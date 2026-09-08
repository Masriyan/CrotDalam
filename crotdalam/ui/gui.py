"""Optional Tk desktop: keyword search, evidence details and report export."""

import asyncio
import json
import queue
import threading


def launch(settings=None):
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
    except ImportError as exc:
        raise RuntimeError("GUI requires Tkinter (install your OS python3-tk package)") from exc
    from crotdalam.reports import generate
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise RuntimeError(f"Cannot open GUI display: {exc}") from exc
    root.title("Crotdalam | Evidence Workspace")
    root.geometry("1100x740")
    root.minsize(640, 480)
    root.configure(background="#14201f")
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background="#14201f", foreground="#e2ece7", fieldbackground="#21332f")
    style.configure("Treeview", background="#21332f", foreground="#e2ece7", fieldbackground="#21332f", rowheight=28)
    style.map("Treeview", background=[("selected", "#35695b")])
    style.map("TButton", background=[("active", "#35695b"), ("disabled", "#283632")])
    frame = ttk.Frame(root, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="EVIDENCE WORKSPACE", font=("TkFixedFont", 13)).pack(anchor="w")
    ttk.Label(frame, text="Keyword search and offline report export", font=("TkDefaultFont", 20)).pack(anchor="w", pady=(6, 20))
    toolbar = ttk.Frame(frame)
    toolbar.pack(fill="x")
    keyword = tk.StringVar()
    entry = ttk.Entry(toolbar, textvariable=keyword)
    entry.pack(side="left", fill="x", expand=True, padx=(0, 12))
    events = queue.Queue()
    records = []
    busy = False
    status = tk.StringVar(value="Ready. Results show the full database snapshot, including existing evidence.")

    def worker(query):
        async def collect():
            from .cli import load_engine
            Engine = load_engine("gui search")
            async with Engine(settings) as engine:
                await engine.search(query, limit=20)
                return list(engine.db.records())
        try:
            events.put(("results", asyncio.run(collect())))
        except Exception as exc:
            events.put(("error", str(exc)))

    def search():
        nonlocal busy
        if busy or not keyword.get().strip():
            return
        busy = True
        search_button.configure(state="disabled")
        export_button.configure(state="disabled")
        status.set("Searching... Please wait for collection and database cleanup.")
        threading.Thread(target=worker, args=(keyword.get().strip(),), daemon=False).start()

    search_button = ttk.Button(toolbar, text="Search", command=search)
    search_button.pack(side="left")
    entry.bind("<Return>", lambda event: search())
    pane = ttk.Frame(frame)
    pane.pack(fill="both", expand=True, pady=18)
    tree = ttk.Treeview(pane, columns=("type", "target", "time"), show="headings")
    for key, label in (("type", "Type"), ("target", "Target"), ("time", "Captured")):
        tree.heading(key, text=label)
        tree.column(key, width=180, minwidth=90)
    scroll = ttk.Scrollbar(pane, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    details = tk.Text(frame, height=10, background="#0d1715", foreground="#dce9e1", wrap="word", state="disabled")
    details.pack(fill="both")

    def select(event):
        selected = tree.selection()
        if selected:
            details.configure(state="normal")
            details.delete("1.0", "end")
            details.insert("end", json.dumps(records[int(selected[0])], indent=2, ensure_ascii=False))
            details.configure(state="disabled")

    tree.bind("<<TreeviewSelect>>", select)
    bottom = ttk.Frame(frame)
    bottom.pack(fill="x", pady=(14, 0))
    format_var = tk.StringVar(value="html")
    ttk.Combobox(bottom, textvariable=format_var, values=("html", "json", "csv", "pdf"), state="readonly", width=8).pack(side="left")

    def export():
        format = format_var.get()
        output = filedialog.asksaveasfilename(parent=root, defaultextension=f".{format}", filetypes=[(format.upper(), f"*.{format}")])
        if not output:
            return
        export_button.configure(state="disabled")
        search_button.configure(state="disabled")
        nonlocal busy
        busy = True
        status.set("Exporting report...")

        def write():
            try:
                events.put(("export", str(generate(records, output, format))))
            except Exception as exc:
                events.put(("error", str(exc)))
        threading.Thread(target=write, daemon=False).start()

    export_button = ttk.Button(bottom, text="Export Report", command=export)
    export_button.pack(side="left", padx=10)
    ttk.Label(frame, textvariable=status, wraplength=850).pack(anchor="w", pady=(10, 0))

    def poll():
        nonlocal busy, records
        try:
            while True:
                kind, payload = events.get_nowait()
                busy = False
                search_button.configure(state="normal")
                export_button.configure(state="normal")
                if kind == "results":
                    records = payload
                    for item in tree.get_children():
                        tree.delete(item)
                    details.configure(state="normal")
                    details.delete("1.0", "end")
                    details.configure(state="disabled")
                    for index, record in enumerate(records):
                        tree.insert("", "end", iid=str(index), values=(record["data_type"], record["target"], record["timestamp"]))
                    status.set(f"{len(records)} records in database snapshot. Select a row to inspect provenance.")
                elif kind == "export":
                    status.set(f"Report exported: {payload}")
                else:
                    status.set("Operation failed. Previous results retained.")
                    messagebox.showerror("Operation failed", payload, parent=root)
        except queue.Empty:
            root.after(100, poll)

    def close():
        if busy:
            messagebox.showinfo("Operation in progress", "Wait for the active operation to finish before closing.", parent=root)
        else:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    root.after(100, poll)
    entry.focus_set()
    root.mainloop()
