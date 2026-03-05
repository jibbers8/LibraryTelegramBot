import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
from typing import Optional

from parser import NaturalLanguageParser, BookingRequest
from browser import BookingAutomation


class BookingApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("UA Library Room Booker")
        self.root.geometry("600x500")
        self.root.resizable(True, True)
        self.root.minsize(500, 400)

        self.parser = NaturalLanguageParser()
        self.automation: Optional[BookingAutomation] = None
        self.booking_thread: Optional[threading.Thread] = None

        self._create_widgets()
        self._center_window()

    def _center_window(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="UA Library Room Booker", font=("Segoe UI", 18, "bold")).pack(pady=(0, 5))
        ttk.Label(main_frame, text="Enter your booking request in natural language", font=("Segoe UI", 10)).pack(pady=(0, 15))

        input_frame = ttk.LabelFrame(main_frame, text="Your Request", padding="10")
        input_frame.pack(fill=tk.X, pady=(0, 15))

        self.input_text = ttk.Entry(input_frame, font=("Segoe UI", 12))
        self.input_text.pack(fill=tk.X, pady=(0, 10))
        self.input_text.insert(0, "a room for 4 people on Tuesday around 4pm")
        self.input_text.bind("<Return>", lambda e: self._on_book_click())

        ttk.Label(input_frame, text="Examples: 'quiet study for tomorrow morning' | 'group room for 6 on Friday at 2pm'",
                  font=("Segoe UI", 9), foreground="gray").pack()

        options_frame = ttk.Frame(main_frame)
        options_frame.pack(fill=tk.X, pady=(10, 15))

        self.accept_similar_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Accept similar times if exact time not available",
                        variable=self.accept_similar_var).pack(side=tk.LEFT)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 15))

        self.preview_btn = ttk.Button(button_frame, text="Preview", command=self._on_preview_click, width=15)
        self.preview_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.book_btn = ttk.Button(button_frame, text="Book Room", command=self._on_book_click, width=15)
        self.book_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.cancel_btn = ttk.Button(button_frame, text="Cancel", command=self._on_cancel_click, width=15, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.LEFT)

        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.pack(fill=tk.BOTH, expand=True)

        self.status_text = scrolledtext.ScrolledText(status_frame, height=12, font=("Consolas", 10),
                                                      state=tk.DISABLED, wrap=tk.WORD)
        self.status_text.pack(fill=tk.BOTH, expand=True)

        self.progress = ttk.Progressbar(main_frame, mode="indeterminate", length=300)
        self.progress.pack(fill=tk.X, pady=(15, 0))

        style = ttk.Style()
        for theme in ["vista", "clam"]:
            if theme in style.theme_names():
                style.theme_use(theme)
                break

    def _log_status(self, message: str):
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, f"{message}\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def _clear_status(self):
        self.status_text.config(state=tk.NORMAL)
        self.status_text.delete(1.0, tk.END)
        self.status_text.config(state=tk.DISABLED)

    def _set_ui_state(self, booking_active: bool):
        state = tk.DISABLED if booking_active else tk.NORMAL
        cancel_state = tk.NORMAL if booking_active else tk.DISABLED
        self.book_btn.config(state=state)
        self.preview_btn.config(state=state)
        self.cancel_btn.config(state=cancel_state)
        if booking_active:
            self.progress.start(10)
        else:
            self.progress.stop()

    def _on_preview_click(self):
        text = self.input_text.get().strip()
        if not text:
            messagebox.showwarning("Empty Input", "Please enter a booking request.")
            return

        self._clear_status()
        self._log_status("Parsing your request...\n")
        try:
            request = self.parser.parse(text)
            self._log_status(f"Interpreted request:\n{'-' * 40}\n{request}\n{'-' * 40}")
            self._log_status("\nClick 'Book Room' to proceed with this booking.")
        except Exception as e:
            self._log_status(f"Error parsing request: {str(e)}")

    def _on_book_click(self):
        text = self.input_text.get().strip()
        if not text:
            messagebox.showwarning("Empty Input", "Please enter a booking request.")
            return

        try:
            request = self.parser.parse(text)
        except Exception as e:
            messagebox.showerror("Parse Error", f"Could not understand request: {str(e)}")
            return

        if not messagebox.askyesno("Confirm Booking", f"Book a room with these details?\n\n{request}"):
            return

        self._start_booking(request)

    def _start_booking(self, request: BookingRequest):
        self._clear_status()
        self._log_status(f"Starting booking process...\n\nRequest details:\n{request}\n\n{'-' * 40}\n")
        self._set_ui_state(True)

        self.automation = BookingAutomation(
            headless=False,
            status_callback=lambda msg: self.root.after(0, lambda: self._log_status(msg)),
            accept_similar_times=self.accept_similar_var.get()
        )

        self.booking_thread = threading.Thread(target=self._booking_worker, args=(request,), daemon=True)
        self.booking_thread.start()

    def _booking_worker(self, request: BookingRequest):
        try:
            success = self.automation.book_room(request)
            self.root.after(0, lambda: self._booking_complete(success))
        except Exception as e:
            self.root.after(0, lambda: self._booking_error(str(e)))

    def _booking_complete(self, success: bool):
        self._set_ui_state(False)
        if success:
            self._log_status(f"\n{'=' * 40}\nBOOKING SUCCESSFUL!\n{'=' * 40}")
            messagebox.showinfo("Success", "Room booked successfully!")
        else:
            self._log_status(f"\n{'=' * 40}\nBooking could not be completed automatically.\nPlease check the browser window.\n{'=' * 40}")

    def _booking_error(self, error: str):
        self._set_ui_state(False)
        self._log_status(f"\nError: {error}")
        messagebox.showerror("Booking Error", f"An error occurred: {error}")

    def _on_cancel_click(self):
        if self.automation:
            try:
                self.automation.close_browser()
            except Exception:
                pass
        self._set_ui_state(False)
        self._log_status("\nBooking cancelled by user.")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    BookingApp().run()
