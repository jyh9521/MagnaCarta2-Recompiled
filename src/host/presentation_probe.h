#pragma once

// Uses public SDK UI contracts; contains no copied window/event implementation.
#include <rex/system/interfaces/graphics.h>
#include <rex/ui/window.h>
#include <rex/ui/window_listener.h>
#include <rex/ui/windowed_app_context_sdl.h>
#include <Windows.h>
#include <cstdio>
#include <memory>

namespace mc2::host {

class PresentationSession final : public rex::ui::WindowListener {
 public:
  PresentationSession() = default;
  PresentationSession(const PresentationSession&) = delete;
  PresentationSession& operator=(const PresentationSession&) = delete;
  ~PresentationSession() override { Shutdown(); }

  // UI thread only. Graphics must not have SetupGuestGpu called beforehand.
  // The caller owns graphics and must keep it alive until Shutdown detaches.
  bool Initialize(rex::system::IGraphicsSystem* graphics) {
    if (context_ || !graphics) return false;
    context_ = std::make_unique<rex::ui::SDLWindowedAppContext>();
    if (!context_->Initialize()) {
      std::puts("PRESENTATION_CONTEXT initialized=0");
      return false;
    }
    std::puts("PRESENTATION_CONTEXT initialized=1 ui_thread=1");
    const auto status = graphics->SetupPresentation(context_.get());
    std::printf("PRESENTATION_SETUP status=%08X has_presentation=%u presenter=%u\n",
                unsigned(status), unsigned(graphics->has_presentation()),
                unsigned(graphics->presenter() != nullptr));
    if (status || !graphics->has_presentation() || !graphics->presenter()) return false;
    window_ = rex::ui::Window::Create(*context_, "MagnaCarta 2 presentation probe", 640, 360);
    if (!window_) return false;
    window_->AddListener(this);
    if (!window_->Open()) return false;
    // SDK Window documents this as HWND on Windows. No SDK visibility setting
    // is provided. Hide immediately after Open; no promise of a pre-Open hide.
    auto hwnd = static_cast<HWND>(window_->GetNativeWindowHandle());
    if (!hwnd || !IsWindow(hwnd)) return false;
    ShowWindow(hwnd, SW_HIDE);
    window_->SetPresenter(graphics->presenter());
    const bool open = window_->phase() == rex::ui::Window::Phase::kOpen;
    const bool hidden = IsWindowVisible(hwnd) == FALSE;
    std::printf("PRESENTATION_WINDOW open=%u hidden=%u binding_requested=1\n",
                unsigned(open), unsigned(hidden));
    return open && hidden;
  }

  rex::ui::SDLWindowedAppContext* context() const { return context_.get(); }
  rex::ui::Window* window() const { return window_.get(); }

  // Blocking SDK event loop, never a private ProcessEvent replacement.
  int Pump() {
    if (!context_ || !context_->IsInUIThread() || !window_) return 4;
    std::puts("PRESENTATION_LOOP enter=1");
    const int status = context_->RunMainMessageLoop();
    std::printf("PRESENTATION_LOOP exit=%d\n", status);
    return status;
  }

  // Cross-thread safe while this session/context is alive. Does not close the
  // window or detach GPU objects; callers must stop/join their observer first.
  void RequestStop() {
    if (context_) context_->RequestDeferredQuit();
  }

  // UI thread only, AFTER active guest/GPU work has stopped. Leaves the context
  // alive for caller-owned Runtime/graphics shutdown until session destruction.
  void Shutdown() {
    if (!context_ || shutdown_) return;
    if (!context_->IsInUIThread()) {
      std::puts("PRESENTATION_SHUTDOWN wrong_ui_thread=1");
      return;
    }
    shutdown_ = true;
    context_->ExecutePendingFunctionsFromUIThread();
    if (window_) {
      auto hwnd = static_cast<HWND>(window_->GetNativeWindowHandle());
      window_->SetPresenter(nullptr);
      window_->RequestClose();
      const bool closed = window_->phase() == rex::ui::Window::Phase::kClosedOpenable;
      window_->RemoveListener(this);
      window_.reset();
      std::printf("PRESENTATION_WINDOW_CLOSED closed=%u native_destroyed=%u\n",
                  unsigned(closed), unsigned(!hwnd || !IsWindow(hwnd)));
      clean_shutdown_ = closed && (!hwnd || !IsWindow(hwnd));
    }
    context_->ExecutePendingFunctionsFromUIThread();
  }

  bool clean_shutdown() const { return clean_shutdown_; }
  bool OnCloseRequested(rex::ui::UIEvent&) override {
    RequestStop();
    return false;  // Caller stops guest/GPU before explicit Shutdown closes.
  }
  void OnClosing(rex::ui::UIEvent&) override {
    if (context_) context_->RequestDeferredQuit();
  }

 private:
  std::unique_ptr<rex::ui::SDLWindowedAppContext> context_;
  std::unique_ptr<rex::ui::Window> window_;
  bool shutdown_ = false;
  bool clean_shutdown_ = false;
};

}  // namespace mc2::host
