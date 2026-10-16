"""Public-contract checks plus an optional synthetic C++ mock; no SDK execution."""
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT/'src/host/wait_observation.h'


class WaitObservationContractTests(unittest.TestCase):
    def setUp(self):self.source=HEADER.read_text(encoding='utf-8')
    def test_sdk_attestation_gate(self):
        self.assertIn('e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a',self.source)
        self.assertLess(self.source.index('if (!sdk_identity_verified)'),self.source.index('table->LookupObject'))
        self.assertIn('"unsupported-sdk"',self.source)
    def test_nonblocking_region(self):
        self.assertIn('region.TryAcquire()',self.source)
        self.assertNotIn('AcquireDirect()',self.source)
        self.assertIn('"busy"',self.source)
        self.assertGreater(self.source.index('std::printf('),self.source.index('// Unknown fields'))
    def test_only_type_query(self):
        calls=re.findall(r'event->Query\(([^;]+)\);',self.source)
        self.assertEqual(calls,['&snapshot.event_type, nullptr'])
    def test_no_state_changing_calls_or_private_offsets(self):
        for forbidden in ('Wait(', 'Set(', 'Pulse(', 'Reset(', 'Clear(', 'ReleaseSemaphore(',
                          'Save(', 'Restore(', 'AddHandle(', 'RemoveHandle(', 'Delete('):
            self.assertNotRegex(self.source,r'->'+re.escape(forbidden))
        self.assertNotIn('reinterpret_cast',self.source)
        self.assertNotIn('pointer_ref_count_',self.source)
        self.assertNotIn('TranslateVirtual',self.source)
    def test_unknown_state_explicit(self):
        for text in ('event_signal_known=0','semaphore_count_known=0','refcount_known=0','producer_known=0'):
            self.assertIn(text,self.source)
    def test_name_is_bounded_and_log_injection_resistant(self):
        self.assertIn('std::array<char, 257>',self.source)
        self.assertIn('std::min<size_t>(name.size(), 128)',self.source)
        self.assertIn('"0123456789ABCDEF"',self.source)
        self.assertNotIn('name.c_str()',self.source)
    def test_typed_lookup_and_public_metadata(self):
        for name in ('XObject','XEvent','XSemaphore','XThread'):
            self.assertIn('LookupObject<rex::system::'+name+'>',self.source)
        self.assertIn('semaphore->maximum_count()',self.source)
        self.assertIn('thread->is_running()',self.source)


MOCK = r'''
#pragma once
#include <mutex>
#include <string>
#include <vector>
#include <type_traits>
#include <cstdint>
namespace rex::thread {
class global_critical_region {
public:
 static std::recursive_mutex& mutex(){static std::recursive_mutex value;return value;}
 auto TryAcquire(){return std::unique_lock<std::recursive_mutex>(mutex(),std::try_to_lock);}
};
}
namespace rex::system {
inline int lookups=0, queries=0, bad_state_queries=0;
class XObject {
public:
 static constexpr uint32_t kHandleBase=0xF8000000;
 enum class Type:uint32_t {Undefined,Enumerator,Event,File,IOCompletion,Module,Mutant,NotifyListener,Semaphore,Session,Socket,SymbolicLink,Thread,Timer};
 explicit XObject(Type t):kind(t){} virtual ~XObject()=default;
 Type type()const{return kind;} uint32_t guest_object()const{return 0x1000;}
 bool is_host_object()const{return false;} const std::string& name()const{return label;}
 std::vector<uint32_t>& handles(){return aliases;}
 Type kind;std::string label="name\nfixture";std::vector<uint32_t> aliases{0xF80000AC};
};
class XEvent:public XObject {
public: XEvent():XObject(Type::Event){} bool signal=true;
 void Query(uint32_t* type,uint32_t* state){++queries;if(type)*type=1;if(state){++bad_state_queries;signal=false;*state=1;}}
};
class XSemaphore:public XObject {
public:XSemaphore():XObject(Type::Semaphore){} int maximum_count()const{return 7;}
};
class XThread:public XObject {
public:XThread():XObject(Type::Thread){} uint32_t thread_id()const{return 42;} bool is_running()const{return true;}
};
template<class T>class object_ref {T* value;
public:explicit object_ref(T* p=nullptr):value(p){} explicit operator bool()const{return value!=nullptr;} T* operator->(){return value;}
};
class ObjectTable {
public:XObject* value=nullptr;
 template<class T>object_ref<T> LookupObject(uint32_t handle){
  ++lookups;if(handle!=0xF80000AC||!value)return object_ref<T>();
  if constexpr(std::is_same_v<T,XObject>)return object_ref<T>(value);
  else return object_ref<T>(dynamic_cast<T*>(value));
 }
};
class KernelState {ObjectTable table;
public:ObjectTable* object_table(){return &table;}
};
}
'''

PROGRAM = r'''
#include "src/host/wait_observation.h"
#include <thread>
#include <atomic>
int main(){
 using namespace rex::system;KernelState kernel;XEvent event;kernel.object_table()->value=&event;
 mc2::host::ObserveWaitObject(&kernel,0,0xF80000AC,false);
 mc2::host::ObserveWaitObject(nullptr,1,0xF80000AC,true);
 mc2::host::ObserveWaitObject(&kernel,2,3,true);
 if(lookups)return 1;
 mc2::host::ObserveWaitObject(&kernel,3,0xF80000B0,true);
 mc2::host::ObserveWaitObject(&kernel,4,0xF80000AC,true);
 if(!event.signal||bad_state_queries||queries!=1)return 2;
 XSemaphore semaphore;kernel.object_table()->value=&semaphore;
 mc2::host::ObserveWaitObject(&kernel,5,0xF80000AC,true);
 XThread thread;kernel.object_table()->value=&thread;
 mc2::host::ObserveWaitObject(&kernel,6,0xF80000AC,true);
 std::atomic<bool> locked=false,done=false;
 std::thread holder([&]{std::lock_guard<std::recursive_mutex> lock(rex::thread::global_critical_region::mutex());locked=true;while(!done)std::this_thread::yield();});
 while(!locked)std::this_thread::yield();
 auto previous=lookups;mc2::host::ObserveWaitObject(&kernel,7,0xF80000AC,true);
 done=true;holder.join();if(lookups!=previous)return 3;
 return 0;
}
'''


class WaitObservationMockTests(unittest.TestCase):
    def test_guard_paths_and_nonconsuming_event(self):
        compiler=shutil.which('c++') or shutil.which('clang++') or shutil.which('g++')
        if not compiler:self.skipTest('no host C++ compiler on PATH; real SDK build verified separately')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for path in ('system/kernel_state.h','system/xevent.h','system/xsemaphore.h','system/xthread.h','thread/mutex.h'):
                target=root/'rex'/path;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text(MOCK if path=='system/kernel_state.h' else '#pragma once\n',encoding='utf-8')
            source=root/'mock.cpp';source.write_text(PROGRAM,encoding='utf-8')
            exe=root/'mock.exe'
            command=[compiler,'-std=c++20','-pthread','-I'+str(root),'-I'+str(ROOT),str(source),'-o',str(exe)]
            built=subprocess.run(command,capture_output=True,text=True,timeout=60)
            self.assertEqual(built.returncode,0,built.stdout+built.stderr)
            result=subprocess.run([str(exe)],capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('status=unsupported-sdk',result.stdout)
            self.assertIn('status=busy',result.stdout)
            self.assertIn('type_name=event',result.stdout)
            self.assertIn('event_type_known=1 event_type=1 event_signal_known=0',result.stdout)
            self.assertIn('semaphore_maximum_known=1 semaphore_maximum=7',result.stdout)
            self.assertIn('thread_metadata_known=1 thread_id=42 thread_running=1',result.stdout)
            self.assertIn('name_hex=6E616D650A66697874757265',result.stdout)


if __name__=='__main__':unittest.main()
