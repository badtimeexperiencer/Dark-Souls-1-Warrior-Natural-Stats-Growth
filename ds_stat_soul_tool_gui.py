"""
Dark Souls Stat & Souls Manager — GUI version (Tkinter)

This version upgrades the earlier CLI prototype into a simple Tkinter GUI.
FIXED: Implemented persistent area index tracking to prevent the drops list
       from clearing when clicking on it, ensuring the 'Delete Drop' button works.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
import os
import math
from copy import deepcopy

SAVE_FILENAME = "ds_game_state_gui.json"

STARTING_CLASSES = {
    "Warrior": {
        "Vitality": 11,
        "Attunement": 8,
        "Endurance": 12,
        "Strength": 13,
        "Dexterity": 13,
        "Resistance": 11,
        "Intelligence": 9,
        "Faith": 9,
    }
}

# ------------------ Data utilities ----------------------------------------

def fresh_state():
    return {
        "starting_class": "Warrior",
        "base_stats": deepcopy(STARTING_CLASSES["Warrior"]),
        "current_stats": deepcopy(STARTING_CLASSES["Warrior"]),
        "souls_by_area": {},
        "souls_used_for_leveling": [],
        "merchant_checklist": {},
        "game_status": "",
    }


def load_state(filename=SAVE_FILENAME):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return fresh_state()


def save_state(state, filename=SAVE_FILENAME):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

# Souls totals

def total_accumulated_souls(state):
    return sum(sum(drops) for drops in state["souls_by_area"].values() if isinstance(drops, list))


def total_souls_used(state):
    return sum(state["souls_used_for_leveling"]) if state["souls_used_for_leveling"] else 0


def remaining_souls(state):
    return total_accumulated_souls(state) - total_souls_used(state)

# Exponential math

def compute_common_r(N0_values, L):
    if L <= 0:
        return 0.0
    S0 = sum(N0_values)
    if S0 <= 0:
        return 0.0
    return math.log(1.0 + float(L) / float(S0)) / float(L)


def continuous_targets(N0_map, r, t):
    return {k: v * math.exp(r * t) for k, v in N0_map.items()}


def greedy_next_stat_to_increment(N0_map, current_map, L_horizon, t_now):
    r = compute_common_r(list(N0_map.values()), L_horizon)
    S = continuous_targets(N0_map, r, t_now)
    # Deficit is the target minus the current value
    deficits = {k: S[k] - current_map[k] for k in N0_map}
    # Choose the stat with the largest deficit, then largest base stat value, then lexicographically
    choice = max(deficits.items(), key=lambda x: (x[1], N0_map[x[0]], x[0]))[0]
    return choice, deficits, r

# ------------------ GUI app -----------------------------------------------

class DSApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Dark Souls Stat & Souls Manager")
        self.geometry("900x600")
        self.state = load_state()
        
        # FIX 1: New attribute to store the persistent index of the selected area
        self.selected_area_index = None 
        
        # Attribute to store the last computed stat for the apply button
        self.last_computation = None 

        # Notebook tabs
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill=tk.BOTH, expand=True)

        self.tab_overview = ttk.Frame(self.nb)
        self.tab_souls = ttk.Frame(self.nb)
        self.tab_leveling = ttk.Frame(self.nb)
        self.tab_merchants = ttk.Frame(self.nb)

        self.nb.add(self.tab_overview, text="Game Overview")
        self.nb.add(self.tab_souls, text="Souls Tracker")
        self.nb.add(self.tab_leveling, text="Leveling Tracker")
        self.nb.add(self.tab_merchants, text="Merchant Checklist")

        self.create_overview_tab()
        self.create_souls_tab()
        self.create_leveling_tab()
        self.create_merchants_tab()

        # Save/Load buttons
        frame_bottom = ttk.Frame(self)
        frame_bottom.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Button(frame_bottom, text="Save", command=self.on_save).pack(side=tk.LEFT, padx=8, pady=6)
        ttk.Button(frame_bottom, text="Load", command=self.on_load).pack(side=tk.LEFT, padx=8, pady=6)

        # Manual update button (user requested manual mode)
        ttk.Button(frame_bottom, text="Update (manual)", command=self.update_all_views).pack(side=tk.RIGHT, padx=8, pady=6)

        self.update_all_views()

    # ---------------- Overview tab -------------------------------------
    def create_overview_tab(self):
        frm = self.tab_overview
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="Game Status:").grid(row=0, column=0, sticky=tk.W, padx=6, pady=6)
        self.ent_status = ttk.Entry(frm)
        self.ent_status.grid(row=0, column=1, sticky=tk.EW, padx=6, pady=6)

        ttk.Label(frm, text="Starting class:").grid(row=1, column=0, sticky=tk.W, padx=6, pady=6)
        self.lbl_class = ttk.Label(frm, text=self.state.get("starting_class", "Warrior"))
        self.lbl_class.grid(row=1, column=1, sticky=tk.W, padx=6, pady=6)

        # Stats display
        stats_frame = ttk.LabelFrame(frm, text="Base / Current Stats")
        stats_frame.grid(row=2, column=0, columnspan=2, sticky=tk.EW, padx=6, pady=6)
        self.stats_text = tk.Text(stats_frame, height=10, state=tk.DISABLED) # Make read-only
        self.stats_text.pack(fill=tk.BOTH, expand=True)

        # Souls summary
        sums_frame = ttk.LabelFrame(frm, text="Souls Summary")
        sums_frame.grid(row=3, column=0, columnspan=2, sticky=tk.EW, padx=6, pady=6)
        self.lbl_total_acc = ttk.Label(sums_frame, text="Total accumulated souls: 0")
        self.lbl_total_used = ttk.Label(sums_frame, text="Total souls used for leveling: 0")
        self.lbl_remaining = ttk.Label(sums_frame, text="Remaining souls: 0")
        self.lbl_total_acc.pack(anchor=tk.W, padx=6, pady=2)
        self.lbl_total_used.pack(anchor=tk.W, padx=6, pady=2)
        self.lbl_remaining.pack(anchor=tk.W, padx=6, pady=2)

        ttk.Button(frm, text="Apply Game Status", command=self.apply_status).grid(row=4, column=1, sticky=tk.E, padx=6, pady=6)

    def apply_status(self):
        self.state["game_status"] = self.ent_status.get().strip()
        messagebox.showinfo("Status", "Game status updated")

    # ---------------- Souls tab ----------------------------------------
    def create_souls_tab(self):
        frm = self.tab_souls
        left = ttk.Frame(frm)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=6)
        right = ttk.Frame(frm)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=6, pady=6)

        ttk.Label(left, text="Areas:").pack(anchor=tk.W)
        self.lb_areas = tk.Listbox(left, height=20)
        self.lb_areas.pack(fill=tk.Y, expand=True)
        # BINDING: Update drops list when a new area is selected
        self.lb_areas.bind('<<ListboxSelect>>', self.on_area_select) 
        ttk.Button(left, text="Add Area", command=self.add_area_dialog).pack(fill=tk.X, pady=4)
        ttk.Button(left, text="Delete Area", command=self.delete_selected_area).pack(fill=tk.X)

        ttk.Label(right, text="Drops in selected area:").pack(anchor=tk.W)
        # FIX 2 (from previous attempt): Set selectmode=tk.SINGLE 
        self.lb_drops = tk.Listbox(right, height=15, selectmode=tk.SINGLE) 
        self.lb_drops.pack(fill=tk.BOTH, expand=True)

        frm_controls = ttk.Frame(right)
        frm_controls.pack(fill=tk.X, pady=6)
        ttk.Button(frm_controls, text="Add Drop", command=self.add_drop_dialog).pack(side=tk.LEFT)
        ttk.Button(frm_controls, text="Delete Drop", command=self.delete_selected_drop).pack(side=tk.LEFT, padx=6)
    
    # New method to handle area selection and update drops list
    def on_area_select(self, event):
        sel = self.lb_areas.curselection()
        if sel:
            # FIX 3: Store the index of the newly selected area persistently
            self.selected_area_index = sel[0]
        else:
            self.selected_area_index = None # If event fires with no selection, clear index
            
        self.update_drops_list()

    def add_area_dialog(self):
        area = simpledialog.askstring("Add Area", "Enter area name:")
        if area:
            area = area.strip().title()
            if area in self.state["souls_by_area"]:
                messagebox.showwarning("Exists", "Area already exists")
                return
            self.state["souls_by_area"][area] = []
            self.state["merchant_checklist"].setdefault(area, {})
            self.update_all_views()

    def delete_selected_area(self):
        sel = self.lb_areas.curselection()
        if not sel:
            return
        area = self.lb_areas.get(sel[0])
        if messagebox.askyesno("Delete", f"Delete area {area} and its drops?"):
            del self.state["souls_by_area"][area]
            if area in self.state["merchant_checklist"]:
                del self.state["merchant_checklist"][area]
            
            # Update persistent index if the deleted area was the one selected
            if self.selected_area_index is not None and sel[0] == self.selected_area_index:
                 self.selected_area_index = None
                 
            self.update_all_views()

    def add_drop_dialog(self):
        sel = self.lb_areas.curselection()
        if not sel:
            messagebox.showwarning("No area", "Select an area first")
            return
        area = self.lb_areas.get(sel[0])
        val = simpledialog.askinteger("Add Drop", "Souls drop value:", minvalue=1)
        if val is not None:
            self.state["souls_by_area"].setdefault(area, []).append(int(val))
            self.update_all_views()

    def delete_selected_drop(self):
        # FIX 4: Use persistent index logic to retrieve area selection
        sel_area_idx = self.lb_areas.curselection()
        if not sel_area_idx and self.selected_area_index is not None:
             sel_area_idx = (self.selected_area_index,)
        
        sel_drop = self.lb_drops.curselection()
        
        if not sel_area_idx or not sel_drop:
            messagebox.showwarning("Selection Required", "Please select both an Area and a Drop to delete.")
            return
        
        area = self.lb_areas.get(sel_area_idx[0])
        idx = sel_drop[0] 
        
        if messagebox.askyesno("Delete", "Delete selected drop?"):
            del self.state["souls_by_area"][area][idx]
            self.update_all_views()

    # ---------------- Leveling tab -------------------------------------
    def create_leveling_tab(self):
        frm = self.tab_leveling
        left = ttk.Frame(frm)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=6)
        right = ttk.Frame(frm)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=6, pady=6)

        ttk.Label(left, text="Souls used per level-up:").pack(anchor=tk.W)
        self.lb_used = tk.Listbox(left, height=20)
        self.lb_used.pack(fill=tk.Y, expand=True)
        ttk.Button(left, text="Add Level-up (souls used)", command=self.add_levelup_dialog).pack(fill=tk.X, pady=4)
        ttk.Button(left, text="Delete Selected", command=self.delete_selected_used).pack(fill=tk.X)

        # Right: stats and allocation controls
        ttk.Label(right, text="Current stats:").pack(anchor=tk.W)
        self.txt_stats = tk.Text(right, height=10, state=tk.DISABLED) # Make read-only
        self.txt_stats.pack(fill=tk.X, pady=4)

        frm_alloc = ttk.Frame(right)
        frm_alloc.pack(fill=tk.X, pady=6)
        
        # --- REVISED LABELS AND EXPLANATION ---
        
        # Row 0: L and t inputs
        ttk.Label(frm_alloc, text="Total Planned Points (L):").grid(row=0, column=0, sticky=tk.W)
        self.ent_L = ttk.Entry(frm_alloc, width=6)
        self.ent_L.insert(0, "1")
        self.ent_L.grid(row=0, column=1, padx=6, sticky=tk.W)
        
        ttk.Label(frm_alloc, text="Points Allocated So Far (t):").grid(row=0, column=2, sticky=tk.W)
        self.ent_t = ttk.Entry(frm_alloc, width=6)
        self.ent_t.insert(0, "1")
        self.ent_t.grid(row=0, column=3, padx=6, sticky=tk.W)
        
        # Row 1: Explanatory labels (moved computation buttons to row 2)
        ttk.Label(frm_alloc, text="Total points for your final build.", font=('TkDefaultFont', 8)).grid(row=1, column=0, columnspan=2, sticky=tk.W)
        ttk.Label(frm_alloc, text="Total points already spent. (t ≤ L)", font=('TkDefaultFont', 8)).grid(row=1, column=2, columnspan=2, sticky=tk.W)

        # Row 2: Computation and Apply Buttons
        ttk.Button(frm_alloc, text="Compute Next Stat (Greedy)", command=self.compute_next_stat).grid(row=2, column=0, columnspan=2, pady=6, sticky=tk.EW)
        ttk.Button(frm_alloc, text="Apply Next Stat", command=self.apply_next_stat).grid(row=2, column=2, columnspan=2, sticky=tk.EW)
        
        # --------------------------------------

        # Reset button (remains in the 'right' frame for full width)
        ttk.Button(right, text="Reset Stats to Base Values", command=self.reset_current_stats).pack(fill=tk.X, pady=10)
        
        self.lbl_next_stat = ttk.Label(right, text="Next stat: -")
        self.lbl_next_stat.pack(anchor=tk.W, pady=4)
        
        # Frame for deficit information
        self.deficit_frame = ttk.LabelFrame(right, text="Greedy Deficit Information")
        self.deficit_text = tk.Text(self.deficit_frame, height=5, state=tk.DISABLED)
        self.deficit_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.deficit_frame.pack(fill=tk.BOTH, expand=True, pady=6)


    def add_levelup_dialog(self):
        val = simpledialog.askinteger("Add Level-up", "Souls used for this level-up:", minvalue=1)
        if val is not None:
            self.state["souls_used_for_leveling"].append(int(val))
            self.update_all_views()

    def delete_selected_used(self):
        sel = self.lb_used.curselection()
        if not sel:
            return
        idx = sel[0]
        if messagebox.askyesno("Delete", "Delete selected souls cost entry?"):
            del self.state["souls_used_for_leveling"][idx]
            self.update_all_views()

    def compute_next_stat(self):
        try:
            L = int(self.ent_L.get())
            t = int(self.ent_t.get())
            if L <= 0 or t <= 0:
                raise ValueError("L and t must be positive.")
        except ValueError as e:
            messagebox.showwarning("Invalid", f"L and t must be positive integers. Error: {e}")
            return
        
        base = self.state["base_stats"]
        current = self.state["current_stats"]
        
        try:
            stat, deficits, r = greedy_next_stat_to_increment(base, current, L, t)
        except ValueError as e:
            messagebox.showerror("Computation Error", f"Could not compute next stat: {e}")
            return

        self.lbl_next_stat.config(text=f"Next stat (greedy): {stat} (r={r:.6f})")
        
        # Update deficits text area
        s = ""
        for k, v in sorted(deficits.items(), key=lambda x: -x[1]):
            s += f"{k:12s}: {v:.6f}\n"
            
        self.deficit_text.config(state=tk.NORMAL)
        self.deficit_text.delete('1.0', tk.END)
        self.deficit_text.insert(tk.END, s)
        self.deficit_text.config(state=tk.DISABLED)
        
        self.last_computation = (stat, deficits, r, L, t)

    def apply_next_stat(self):
        if not hasattr(self, 'last_computation') or self.last_computation is None:
            messagebox.showwarning("Compute first", "Press Compute Next Stat first")
            return
            
        stat = self.last_computation[0]
        self.last_computation = None 
        
        if isinstance(self.state["current_stats"], dict):
            self.state["current_stats"][stat] = self.state["current_stats"].get(stat, 0) + 1
            messagebox.showinfo("Applied", f"Applied +1 to {stat}. Remember to add souls cost in the list below.")
            self.lbl_next_stat.config(text="Next stat: -") # Clear label after applying
            
            # Clear deficits text area
            self.deficit_text.config(state=tk.NORMAL)
            self.deficit_text.delete('1.0', tk.END)
            self.deficit_text.config(state=tk.DISABLED)

            self.update_all_views()
        else:
            messagebox.showerror("Error", "Current stats data is corrupted.")

    def reset_current_stats(self):
        """Resets the current_stats to the base_stats (starting class values)."""
        if messagebox.askyesno("Reset Stats", "Are you sure you want to reset ALL current stat allocations back to the starting class values? (This will NOT affect the 'Souls Used' list.)"):
            
            # Deepcopy ensures we reset to a fresh copy of the base stats
            self.state["current_stats"] = deepcopy(self.state["base_stats"])
            
            # Reset last computation
            self.last_computation = None
            
            self.update_all_views()
            messagebox.showinfo("Reset Complete", "Current stats have been reset to starting class values.")


    # ---------------- Merchants tab ------------------------------------
    def create_merchants_tab(self):
        frm = self.tab_merchants
        top = ttk.Frame(frm)
        top.pack(fill=tk.X, padx=6, pady=6)
        ttk.Button(top, text="Add Merchant", command=self.add_merchant_dialog).pack(side=tk.LEFT)
        ttk.Button(top, text="Toggle Bought", command=self.toggle_merchant_bought).pack(side=tk.LEFT, padx=6)

        # The Treeview is configured correctly here
        self.tree_merchants = ttk.Treeview(frm, columns=('Status',), show='tree headings')
        self.tree_merchants.column('#0', width=250, anchor=tk.W)
        self.tree_merchants.heading('#0', text='Area / Merchant')
        self.tree_merchants.column('Status', width=100, anchor=tk.CENTER)
        self.tree_merchants.heading('Status', text='Status')
        
        self.tree_merchants.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    def add_merchant_dialog(self):
        area = simpledialog.askstring("Area", "Enter area name:")
        if not area:
            return
        name = simpledialog.askstring("Merchant", "Enter merchant name:")
        if not name:
            return
        
        # Normalize area and name case
        area = area.strip().title()
        name = name.strip()
        
        self.state.setdefault("merchant_checklist", {})
        self.state["merchant_checklist"].setdefault(area, {})
        if name in self.state["merchant_checklist"][area]:
             messagebox.showwarning("Exists", f"Merchant '{name}' already exists in {area}.")
             return
             
        self.state["merchant_checklist"][area][name] = False
        self.update_all_views()

    def toggle_merchant_bought(self):
        sel = self.tree_merchants.selection()
        if not sel:
            return
        node = sel[0]
        parent = self.tree_merchants.parent(node)
        if parent == '':
            messagebox.showwarning("Select merchant", "Select a merchant (not area) to toggle.")
            return
            
        # Get area name from parent node
        area = self.tree_merchants.item(parent, 'text')
        # Get merchant name from child node
        merchant = self.tree_merchants.item(node, 'text')
        
        try:
            cur = self.state["merchant_checklist"][area][merchant]
            self.state["merchant_checklist"][area][merchant] = not cur
            self.update_all_views()
        except KeyError:
            messagebox.showerror("Error", "Area or merchant not found in state.")

    # ---------------- Update views -------------------------------------
    def update_drops_list(self):
        """Updates the drops list based on the currently selected area (using persistent index if needed)."""
        
        # Prioritize instantaneous selection, but fall back to the persistent index
        sel_idx = self.lb_areas.curselection()
        if not sel_idx and self.selected_area_index is not None:
             sel_idx = (self.selected_area_index,) # Use persistent index

        # Clear the drops list
        self.lb_drops.delete(0, tk.END)
        
        # Proceed only if an area is currently selected (instantaneous or persistent)
        if sel_idx:
            area_index = sel_idx[0]
            
            # Defensive check: ensure the index is still valid
            if area_index < self.lb_areas.size():
                area = self.lb_areas.get(area_index)
                for v in self.state["souls_by_area"].get(area, []):
                    self.lb_drops.insert(tk.END, str(v))
    
    # REVISED update_all_views
    def update_all_views(self):
        # ... (Overview and Stats updates remain the same) ...
        self.ent_status.delete(0, tk.END)
        self.ent_status.insert(0, self.state.get('game_status', ''))
        self.lbl_class.config(text=self.state.get('starting_class', 'Warrior'))

        self.stats_text.config(state=tk.NORMAL) 
        self.stats_text.delete('1.0', tk.END)
        s = "Base stats:\n"
        for k, v in self.state["base_stats"].items():
            s += f"  {k:12s}: {v}\n"
        s += "\nCurrent stats:\n"
        for k, v in self.state["current_stats"].items():
            s += f"  {k:12s}: {v}\n"
        self.stats_text.insert(tk.END, s)
        self.stats_text.config(state=tk.DISABLED) 

        self.lbl_total_acc.config(text=f"Total accumulated souls: {total_accumulated_souls(self.state)}")
        self.lbl_total_used.config(text=f"Total souls used for leveling: {total_souls_used(self.state)}")
        self.lbl_remaining.config(text=f"Remaining souls: {remaining_souls(self.state)}")

        # Souls tab
        # Store selected index (the persistent one, not the instantaneous) to reselect after refresh
        sel_idx_to_restore = self.selected_area_index 
        
        self.lb_areas.delete(0, tk.END)
        for area in sorted(self.state["souls_by_area"].keys()):
            self.lb_areas.insert(tk.END, area)
            
        # Re-select the area if there was one selected and the index is still valid
        if sel_idx_to_restore is not None and sel_idx_to_restore < self.lb_areas.size():
            self.lb_areas.selection_set(sel_idx_to_restore)
            # Ensure the persistent index is maintained
            self.selected_area_index = sel_idx_to_restore
        else:
             # If the area list changed or the index was invalid, reset the persistent index
             self.selected_area_index = None

        self.update_drops_list()

        # ... (Leveling tab and Merchants tab updates remain the same) ...
        self.lb_used.delete(0, tk.END)
        for v in self.state["souls_used_for_leveling"]:
            self.lb_used.insert(tk.END, str(v))
            
        self.txt_stats.config(state=tk.NORMAL) 
        self.txt_stats.delete('1.0', tk.END)
        for k, v in self.state["current_stats"].items():
            self.txt_stats.insert(tk.END, f"{k:12s}: {v}\n")
        self.txt_stats.config(state=tk.DISABLED) 
        
        if not hasattr(self, 'last_computation') or self.last_computation is None:
            self.lbl_next_stat.config(text="Next stat: -")
            self.deficit_text.config(state=tk.NORMAL)
            self.deficit_text.delete('1.0', tk.END)
            self.deficit_text.config(state=tk.DISABLED)

        for n in self.tree_merchants.get_children():
            self.tree_merchants.delete(n)
        for area, merchants in sorted(self.state.get('merchant_checklist', {}).items()):
            aid = self.tree_merchants.insert('', 'end', text=area, open=True, iid=area)
            for m, bought in sorted(merchants.items()):
                tag = '(BOUGHT)' if bought else '(pending)'
                self.tree_merchants.insert(aid, 'end', text=m, values=(tag,))


    # ---------------- Save / Load --------------------------------------
    def on_save(self):
        self.state["game_status"] = self.ent_status.get().strip()
        save_state(self.state)
        messagebox.showinfo("Saved", f"Saved to {SAVE_FILENAME}")

    def on_load(self):
        self.state = load_state()
        self.selected_area_index = None # Reset persistent index on load
        self.last_computation = None 
        self.update_all_views()
        messagebox.showinfo("Loaded", f"Loaded {SAVE_FILENAME}")

# ------------------ Main --------------------------------------------------

if __name__ == '__main__':
    app = DSApp()
    app.mainloop()