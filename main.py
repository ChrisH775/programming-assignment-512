"""Run this file to open the Smart Campus Resource Booking System."""
import os
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from booking import BookingSystem, Lecturer, SystemOperator, check_booking_policy


class BookingApp:
    def __init__(self, root, system):
        self.root=root
        self.system = system
        self.user=None
        self.root.title("Smart Campus Resource Booking System")
        self.root.geometry('1000x720')
        self.root.minsize(850, 650)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.login_screen()
        self.root.after(10000, self.auto_refresh)

    def clear(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def entry(self, frame, label, row, secret=False):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=5)
        field=ttk.Entry(frame,width=30)
        if secret:
            field.config(show='*')
        field.grid(row=row, column=1, padx=5, pady=5)
        return field

    def login_screen(self):
        self.user = None
        if self.system.needs_setup():
            self.account_screen("setup")
        else:
            self.account_screen("login")

    def registration_screen(self):
        self.account_screen("register")

    def account_screen(self, mode):
        self.clear()
        self.account_mode=mode
        frame = ttk.Frame(self.root, padding=30)
        frame.pack(pady=60)
        if mode=="setup":
            title = 'First-time setup'
            ttk.Label(frame, text="Create a password for operator, admin1, admin2 and admin3.").grid(
                row=1, columnspan=2, pady=10)
        else:
            title='Log in'
            if mode == "register":
                title = "Register lecturer"
            self.username = self.entry(frame, "Username", 1)
        ttk.Label(frame, text=title, font=("Arial", 18)).grid(row=0, columnspan=2, pady=20)
        self.password = self.entry(frame, "Password", 2, True)
        if mode != "login":
            self.confirm = self.entry(frame, "Confirm password", 3, True)
            ttk.Label(frame, text="Use at least 8 characters.").grid(row=4, columnspan=2, pady=5)
        ttk.Button(frame, text=title, command=self.submit_account).grid(row=5, columnspan=2, pady=10)
        if mode == "login":
            ttk.Button(frame, text="Register lecturer", command=self.registration_screen).grid(
                row=6, columnspan=2)
        elif mode == "register":
            ttk.Button(frame, text="Back to login", command=self.login_screen).grid(row=6, columnspan=2)

    def submit_account(self):
        try:
            mode=self.account_mode
            if mode != "login" and self.password.get() != self.confirm.get():
                raise ValueError("Passwords do not match.")
            if mode == "setup":
                self.system.setup(self.password.get())
                messagebox.showinfo("Success", "Setup complete. Please log in.")
            elif mode=="register":
                self.system.register(self.username.get(), self.password.get())
                messagebox.showinfo("Success", "Account created. Please log in.")
            else:
                self.user = self.system.login(self.username.get(), self.password.get())
                self.dashboard()
                return
            self.login_screen()
        except (ValueError, sqlite3.Error) as error:
            messagebox.showerror("Error", str(error))

    def dashboard(self):
        self.clear()
        top=ttk.Frame(self.root, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text=self.user.username + " — " + self.user.role_name(),
                  font=("Arial", 14)).pack(side="left")
        ttk.Button(top, text="Log out", command=self.login_screen).pack(side="right")
        campus_frame = ttk.Frame(self.root, padding=10)
        campus_frame.pack(fill="x")
        ttk.Label(campus_frame, text="Active campus:").pack(side="left")
        self.campus_list = self.system.campuses(self.user)
        campus_names=[]
        for campus in self.campus_list:
            campus_names.append(campus["name"])
        self.campus_choice = ttk.Combobox(
            campus_frame, values=campus_names, state="readonly", width=24)
        self.campus_choice.pack(side="left", padx=10)
        self.campus_choice.current(0)
        self.campus_choice.bind("<<ComboboxSelected>>", self.change_campus)
        self.policy_label = ttk.Label(self.root)
        self.policy_label.pack(pady=4)
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)
        self.resource_tab = ttk.Frame(self.tabs, padding=10)
        self.booking_tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(self.resource_tab, text="Resources and availability")
        if isinstance(self.user, Lecturer):
            self.tabs.add(self.booking_tab, text="My bookings")
        else:
            self.tabs.add(self.booking_tab, text="Campus bookings")
        self.build_resources()
        self.build_bookings()
        if not isinstance(self.user, Lecturer):
            self.report_tab = ttk.Frame(self.tabs, padding=10)
            self.tabs.add(self.report_tab, text="Reports")
            ttk.Button(self.report_tab, text="Campus report", command=self.show_campus_report).pack(anchor="w")
            if isinstance(self.user, SystemOperator):
                ttk.Button(self.report_tab, text="Compare all campuses", command=self.show_comparison).pack(
                    anchor="w", pady=5)
            self.report_text = tk.Text(self.report_tab, wrap="word", font=("Arial", 11))
            self.report_text.pack(fill="both", expand=True, pady=10)
        self.change_campus()

    def campus(self):
        return self.campus_list[self.campus_choice.current()]

    def change_campus(self, event=None):
        campus=self.campus()
        self.policy_label.config(text="Booking policy: "
                                 + campus["opens"] + "–" + campus["closes"] + " | Maximum "
                                 + str(campus["max_minutes"]) + " minutes per booking")
        self.refresh_resources()
        self.refresh_bookings()
        if not isinstance(self.user, Lecturer):
            self.show_campus_report()

    def build_resources(self):
        form=ttk.Frame(self.resource_tab)
        form.pack(anchor="w")
        self.date = self.entry(form, "Date (YYYY-MM-DD)", 0)
        self.date.insert(0, (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"))
        self.time = self.entry(form, "Start (HH:MM)", 1)
        self.time.insert(0,'10:00')
        self.duration = self.entry(form, "Duration (minutes)", 2)
        self.duration.insert(0, '60')
        ttk.Button(form, text="Check selected time", command=self.check_time).grid(row=3, column=0, pady=8)
        ttk.Button(form, text="Show availability now", command=self.show_now).grid(row=3, column=1)
        self.availability_label = ttk.Label(self.resource_tab, text="Availability now")
        self.availability_label.pack(anchor="w", pady=5)
        self.resource_tree = self.table(self.resource_tab, ("ID", "Resource", "Availability"), 5)
        self.selected_interval=None
        actions = ttk.Frame(self.resource_tab)
        actions.pack(fill="x", pady=8)
        if isinstance(self.user, Lecturer):
            ttk.Button(actions, text="Book selected resource", command=self.book).pack(side="left")
        else:
            ttk.Label(actions, text="Resource name:").pack(side="left")
            self.resource_name = ttk.Entry(actions, width=27)
            self.resource_name.pack(side="left", padx=5)
            ttk.Button(actions, text="Add", command=self.add_resource).pack(side="left", padx=3)
            ttk.Button(actions, text="Update selected", command=self.update_resource).pack(side="left", padx=3)
            ttk.Button(actions, text="Remove selected", command=self.remove_resource).pack(side="left", padx=3)
            self.resource_tree.bind("<<TreeviewSelect>>", self.fill_resource_name)

    def table(self, parent, columns, height):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=height, selectmode="browse")
        for name in columns:
            tree.heading(name, text=name)
            tree.column(name, width=110, minwidth=45, stretch=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        return tree

    def selected_id(self, tree):
        selection = tree.selection()
        if not selection:
            raise ValueError("Select a row first.")
        return int(selection[0])

    def refresh_resources(self):
        selected=self.resource_tree.selection()
        self.resource_tree.delete(*self.resource_tree.get_children())
        if self.selected_interval:
            start, end = self.selected_interval
        else:
            start = datetime.now().isoformat(timespec="seconds")
            end = (datetime.now() + timedelta(seconds=1)).isoformat(timespec="seconds")
        for resource in self.system.resources(self.user, self.campus()["id"]):
            status='Booked'
            if self.system.is_available(resource["id"], start, end):
                status = "Available"
            self.resource_tree.insert("", "end", iid=str(resource["id"]),
                                      values=(resource["id"], resource["name"], status))
        if selected and self.resource_tree.exists(selected[0]):
            self.resource_tree.selection_set(selected[0])

    def show_now(self):
        self.selected_interval = None
        self.availability_label.config(text="Availability now")
        self.refresh_resources()

    def check_time(self):
        try:
            start, end, minutes = check_booking_policy(
                self.campus(), self.date.get(), self.time.get(), self.duration.get())
            self.selected_interval = (start.isoformat(timespec="minutes"), end.isoformat(timespec="minutes"))
            self.availability_label.config(text="Availability: " + start.strftime("%Y-%m-%d %H:%M")
                                           + " to " + end.strftime("%H:%M"))
            self.refresh_resources()
        except ValueError as error:
            messagebox.showerror("Invalid time", str(error))

    def book(self):
        try:
            booking_id = self.system.book(self.user, self.campus()["id"],
                                          self.selected_id(self.resource_tree),
                                          self.date.get(), self.time.get(), self.duration.get())
            messagebox.showinfo("Booked", f"Booking {booking_id} saved.")
            self.refresh_resources()
            self.refresh_bookings()
        except (ValueError, sqlite3.Error) as error:
            messagebox.showerror("Booking error", str(error))

    def fill_resource_name(self, event=None):
        selection = self.resource_tree.selection()
        if selection:
            self.resource_name.delete(0, "end")
            self.resource_name.insert(0, self.resource_tree.item(selection[0], "values")[1])

    def add_resource(self):
        self.save_resource(False)

    def update_resource(self):
        self.save_resource(True)

    def save_resource(self, update):
        try:
            resource_id = None
            if update:
                resource_id = self.selected_id(self.resource_tree)
            self.system.save_resource(self.user, self.campus()["id"], self.resource_name.get(), resource_id)
            self.refresh_resources()
            self.refresh_bookings()
        except (ValueError, sqlite3.Error) as error:
            messagebox.showerror("Resource error", str(error))

    def remove_resource(self):
        try:
            resource_id = self.selected_id(self.resource_tree)
            if messagebox.askyesno("Remove resource", "Remove this resource?"):
                self.system.remove_resource(self.user, self.campus()["id"], resource_id)
                self.refresh_resources()
        except (ValueError, sqlite3.Error) as error:
            messagebox.showerror("Resource error", str(error))

    def build_bookings(self):
        bar = ttk.Frame(self.booking_tab)
        bar.pack(fill="x", pady=5)
        ttk.Label(bar, text="Show:").pack(side="left")
        self.booking_filter = ttk.Combobox(
            bar, values=["All", "Active", "Past", "Cancelled"], state="readonly", width=15)
        self.booking_filter.pack(side="left", padx=10)
        self.booking_filter.current(0)
        self.booking_filter.bind("<<ComboboxSelected>>", self.refresh_bookings)
        ttk.Button(bar, text="Refresh", command=self.refresh_bookings).pack(side="left")
        if isinstance(self.user, Lecturer):
            ttk.Button(bar, text="Cancel selected booking", command=self.cancel).pack(side="right")
        self.booking_tree = self.table(
            self.booking_tab, ("ID", "Lecturer", "Resource", "Start", "Minutes", "Status"), 12)

    def refresh_bookings(self, event=None):
        self.booking_tree.delete(*self.booking_tree.get_children())
        for booking in self.system.bookings(self.user, self.campus()["id"]):
            status = "Active"
            if booking["cancelled"]:
                status = "Cancelled"
            elif datetime.fromisoformat(booking["end"]) <= datetime.now():
                status = "Past"
            if self.booking_filter.get() not in ("All", status):
                continue
            self.booking_tree.insert("", "end", iid=str(booking["id"]), values=(
                booking["id"], booking["username"], booking["name"],
                booking["start"].replace("T", " "), booking["duration"], status))

    def cancel(self):
        try:
            booking_id = self.selected_id(self.booking_tree)
            if messagebox.askyesno("Cancel booking", "Cancel this future booking?"):
                self.system.cancel(self.user, booking_id)
                self.refresh_bookings()
                self.refresh_resources()
        except (ValueError, sqlite3.Error) as error:
            messagebox.showerror("Cancellation error", str(error))

    def report_lines(self, campus_id):
        report=self.system.report(self.user,campus_id)
        campus = report["campus"]
        lines = [campus["name"], "Policy: " + campus["opens"] + "–" + campus["closes"]]
        lines.append("Maximum session: " + str(campus["max_minutes"]) + " minutes")
        lines.append("Total bookings: {}".format(report["total"]))
        lines.append("Booked time: " + str(report["minutes"]) + " minutes")
        lines.append("Average duration: " + str(round(report["average"], 1)) + " minutes")
        lines.append("Most frequently booked: " + report["most_used"])
        lines.append("Bookings by month:")
        for month in sorted(report["months"]):
            lines.append("  " + month + ": " + str(report["months"][month]))
        if not report["months"]:
            lines.append("  No bookings")
        return "\n".join(lines)

    def write_report(self, text):
        self.report_text.config(state="normal")
        self.report_text.delete("1.0", "end")
        self.report_text.insert("1.0", text)
        self.report_text.config(state="disabled")

    def show_campus_report(self):
        self.write_report("Bookings for all dates (cancelled bookings excluded).\n\n"
                          + self.report_lines(self.campus()["id"]))

    def show_comparison(self):
        sections = ["CAMPUS COMPARISON\nBookings for all dates (cancelled bookings excluded)."]
        for campus in self.campus_list:
            sections.append(self.report_lines(campus["id"]))
        self.write_report("\n\n".join(sections))

    def auto_refresh(self):
        if self.user:
            try:
                self.refresh_resources()
                self.refresh_bookings()
            except sqlite3.Error:
                pass  # A temporary database lock can be retried on the next refresh.
        self.root.after(10000, self.auto_refresh)

    def close(self):
        self.system.close()
        self.root.destroy()


def main():
    folder=os.path.dirname(os.path.abspath(__file__))
    root=tk.Tk()
    try:
        system = BookingSystem(os.path.join(folder, "campus_booking.db"))
    except sqlite3.Error as error:
        messagebox.showerror("Database error", str(error))
        root.destroy()
        return
    BookingApp(root, system)
    root.mainloop()


if __name__ == "__main__":
    main()
