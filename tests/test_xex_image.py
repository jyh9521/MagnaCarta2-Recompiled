import struct
from pathlib import Path
import unittest

from tools.research.probe_native_call import expected_lines
from tools.research.probe_xex_image import compare_loaded, image_layout, import_bindings, validate_image_output


def fixture():
    data=bytearray(512)
    data[:2]=b'MZ'; struct.pack_into('<I',data,0x3c,0x40)
    data[0x40:0x44]=b'PE\0\0'
    struct.pack_into('<H',data,0x46,2);struct.pack_into('<H',data,0x54,64)
    struct.pack_into('<H',data,0x58,0x10b);struct.pack_into('<I',data,0x58+56,768)
    for i,(name,rva,size) in enumerate(((b'.data',300,50),(b'.reloc',450,100))):
        off=0x58+64+i*40;data[off:off+len(name)]=name
        struct.pack_into('<IIII',data,off+8,size,rva,size,rva)
    return bytes(data)


def output():
    return '\n'.join(['RUNTIME_DLL runtime.dll','SETUP status=00000000',
        'REGISTRATION count=58408 base=mapped',
        'IMAGE_LOAD path=game:\\default-disc1.xex status=00000000',
        'IMAGE_MODULE entry=82868EC0 stack=00040000',
        'IMAGE_SNAPSHOT base=82000000 size=20119552',
        'IMAGE_VTABLE operand=82508E60 add=8250BAF0 original=1',
        'IMAGE_GNATIVES zero_slots=4096',
        'IMAGE_SIZES security=20119552 pe_declared=22284288 sdk_pages=20119552',
        'IMAGE_KERNEL tables=3 variables=13',
        'IMAGE_IMPORT library=xam records=91','IMAGE_IMPORT library=xboxkrnl records=168',
        *expected_lines(),'SHUTDOWN complete'])


def binding_fixture():
    image=bytearray(512)
    ordinals=(14,27,89,173,342,344,403,430,446,447,448,449,614)
    addresses=[];lines=[]
    for i,ordinal in enumerate(ordinals):
        address=0x82000100+i*4;addresses.append(address)
        struct.pack_into('>I',image,address-0x82000000,ordinal)
        lines.append(f'IMAGE_VARIABLE library=xboxkrnl ordinal={ordinal} slot={address:08X} actual=30000000 expected=30000000 success=1')
    return bytes(image),{'import_libraries':[{'name':'xboxkrnl.exe','import_record_addresses':addresses}]},'\n'.join(lines)


class ImageTests(unittest.TestCase):
    def test_thirteen_sdk_binding_sources(self):
        image,metadata,lines=binding_fixture()
        self.assertEqual(len(import_bindings(lines,image,metadata)),13)

    def test_missing_duplicate_sdk_binding(self):
        image,metadata,lines=binding_fixture()
        for text in ('\n'.join(lines.splitlines()[1:]),lines+'\n'+lines.splitlines()[0]):
            with self.assertRaisesRegex(ValueError,'thirteen'):
                import_bindings(text,image,metadata)

    def test_binding_not_declared_in_original(self):
        image,metadata,lines=binding_fixture()
        with self.assertRaisesRegex(ValueError,'original import'):
            import_bindings(lines.replace('ordinal=14 ','ordinal=15 '),image,metadata)

    def test_binding_resolver_mismatch(self):
        image,metadata,lines=binding_fixture()
        with self.assertRaisesRegex(ValueError,'original import'):
            import_bindings(lines.replace('expected=30000000','expected=30000001'),image,metadata)

    def test_binding_malformed_rejected(self):
        image,metadata,lines=binding_fixture()
        with self.assertRaisesRegex(ValueError,'malformed'):
            import_bindings(lines.replace('success=1','success=0'),image,metadata)

    def test_binding_type_one_not_variable(self):
        image,metadata,lines=binding_fixture();image=bytearray(image)
        struct.pack_into('>I',image,256,0x0100000e)
        with self.assertRaisesRegex(ValueError,'original import'):
            import_bindings(lines,image,metadata)

    def test_entire_security_image_equal(self):
        data=fixture(); report=compare_loaded(data,data)
        self.assertEqual(report['compared_bytes'],512)
        self.assertEqual(report['different_bytes'],0)
        self.assertEqual(report['original_sha256'],report['loaded_sha256'])

    def test_partial_reloc_explicit(self):
        report=image_layout(fixture())
        self.assertEqual(report['pe_declared_size_of_image'],768)
        self.assertEqual(report['sections'][0]['coverage'],'complete')
        self.assertEqual(report['sections'][1]['coverage'],'partial-security-image')
        self.assertEqual(report['sections'][1]['covered_bytes'],62)

    def test_loaded_extra_bytes_rejected(self):
        with self.assertRaisesRegex(ValueError,'size mismatch'):
            compare_loaded(fixture(),fixture()+b'\0')

    def test_official_variable_slot_exception(self):
        data=bytearray(fixture());struct.pack_into('>I',data,400,0x30000000)
        bindings=[{'address':0x82000190,'value':0x30000000}]
        report=compare_loaded(fixture(),data,bindings)
        self.assertEqual(report['unexplained_different_bytes'],0)
        self.assertEqual(report['different_bytes'],1)
        self.assertNotEqual(report['original_sha256'],report['loaded_sha256'])

    def test_variable_wrong_resolver_value_rejected(self):
        with self.assertRaisesRegex(ValueError,'SDK resolver'):
            compare_loaded(fixture(),fixture(),[{'address':0x82000190,'value':1}])

    def test_static_vtable_change_rejected(self):
        data=bytearray(fixture());data[320]^=1
        with self.assertRaisesRegex(ValueError,'82000140'):
            compare_loaded(fixture(),data)

    def test_unsectioned_gap_change_rejected(self):
        data=bytearray(fixture());data[400]^=1
        with self.assertRaisesRegex(ValueError,'82000190'):
            compare_loaded(fixture(),data)

    def test_bad_header(self):
        for data in (b'',b'MZ'+bytes(2),bytes(512)):
            with self.assertRaises(ValueError):image_layout(data)

    def test_bad_pe_offset(self):
        data=bytearray(fixture());struct.pack_into('<I',data,0x3c,500)
        with self.assertRaisesRegex(ValueError,'PE header'):image_layout(data)

    def test_bad_count_and_optional_bounds(self):
        for offset,value in ((0x46,0),(0x46,97),(0x54,59),(0x54,500)):
            data=bytearray(fixture());struct.pack_into('<H',data,offset,value)
            with self.assertRaisesRegex(ValueError,'bounds'):image_layout(data)

    def test_pe32_profile(self):
        data=bytearray(fixture());struct.pack_into('<H',data,0x58,0x20b)
        with self.assertRaisesRegex(ValueError,'PE32'):image_layout(data)

    def test_address_overflow(self):
        data=bytearray(fixture());struct.pack_into('<II',data,0x58+64+8,100,0xfffffff0)
        with self.assertRaisesRegex(ValueError,'overflow'):image_layout(data)

    def test_runtime_markers(self):
        self.assertTrue(validate_image_output(output(),'runtime.dll'))

    def test_missing_duplicate_marker(self):
        for text in (output().replace('SHUTDOWN complete',''),output()+'\nSHUTDOWN complete'):
            with self.assertRaisesRegex(ValueError,'image marker'):
                validate_image_output(text,'runtime.dll')

    def test_native_output_mismatch(self):
        with self.assertRaisesRegex(ValueError,'eight cases'):
            validate_image_output(output().replace('result=0000002A','result=0000002B'),'runtime.dll')

    def test_nonzero_gnatives_rejected(self):
        with self.assertRaisesRegex(ValueError,'image marker'):
            validate_image_output(output().replace('zero_slots=4096','zero_slots=4095'),'runtime.dll')

    def test_wrong_dll(self):
        with self.assertRaisesRegex(ValueError,'DLL'):
            validate_image_output(output(),'wrong.dll')

    def test_probe_does_not_write_original_static_words(self):
        source=(Path(__file__).parents[1]/'src/host/image_probe.cpp').read_text()
        self.assertNotIn('AllocFixed',source)
        self.assertNotIn('Write32(base, 0x832',source)
        self.assertIn('LoadXexImage(guest)',source)
        self.assertIn('module.reset();',source)


if __name__=='__main__':unittest.main()
