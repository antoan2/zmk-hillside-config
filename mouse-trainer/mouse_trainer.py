#!/usr/bin/env python3
"""
Mouse Trainer - A simple tool to practice quick mouse movements.
Click the button as fast as you can! Each click spawns a new button at a random location.
Complete 5-click rounds and track your times!

Supports multi-monitor setups with offsets - spawns window covering all screens
but only places buttons within actual screen boundaries.
"""

import tkinter as tk
import random
import time
import os
from datetime import datetime

# Try to import screeninfo for multi-monitor support
try:
    from screeninfo import get_monitors
    HAS_SCREENINFO = True
except ImportError:
    HAS_SCREENINFO = False
    print("Note: Install 'screeninfo' package for multi-monitor support: pip install screeninfo")


class MouseTrainer:
    def __init__(self):
        print("=" * 60)
        print("MOUSE TRAINER STARTUP - DEBUG MODE")
        print("=" * 60)
        
        self.root = tk.Tk()
        self.root.title("Mouse Trainer")
        self.root.configure(bg="#2b2b2b")
        
        # Need to update before getting screen info
        self.root.update_idletasks()
        print("[DEBUG] Initial window info:")
        print(f"  winfo_screenwidth: {self.root.winfo_screenwidth()}")
        print(f"  winfo_screenheight: {self.root.winfo_screenheight()}")
        
        # Get monitor information and calculate window bounds
        self.monitors = []
        self.screen_regions = []  # Valid regions where buttons can spawn
        self.setup_multi_monitor()
        
        # Calculate geometry - we want window slightly larger than total screen area
        self.padding = 10
        self.target_width = self.window_width + self.padding * 2
        self.target_height = self.window_height + self.padding * 2
        self.target_x = max(0, self.window_x - self.padding)
        self.target_y = max(0, self.window_y - self.padding)
        
        print("[DEBUG] Target geometry:")
        print(f"  target_width: {self.target_width}, target_height: {self.target_height}")
        print(f"  target_x: {self.target_x}, target_y: {self.target_y}")
        
        # For multi-monitor spanning, we can't use -fullscreen as it only covers one screen
        # Instead, set geometry to span all monitors and use -topmost to stay on top
        # Keep window decorations minimal but allow taskbar and Alt+F4
        
        # Set initial geometry
        self.root.geometry(f"{self.target_width}x{self.target_height}+{self.target_x}+{self.target_y}")
        
        # Set window to stay on top
        self.root.attributes("-topmost", True)
        
        # Remove window decorations but keep in taskbar (type hint)
        # On X11/Linux, we can set window type to make it borderless but still managed
        try:
            self.root.attributes("-type", "splash")  # Splash windows have no decorations
        except tk.TclError:
            # Fallback for systems that don't support -type
            pass
        
        # Handle window close button (X)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Allow escape to exit, Q to quit entirely
        self.root.bind("<Escape>", lambda e: self.on_close())
        self.root.bind("<q>", lambda e: self.on_close())
        self.root.bind("<F11>", self.toggle_fullscreen)
        
        # Ensure the window gets focus for keyboard events
        self.root.focus_force()
        self.root.lift()
        
        self.root.update_idletasks()
        print("[DEBUG] After setup:")
        print(f"  winfo_geometry: {self.root.winfo_geometry()}")
        
        # Circular button dimensions
        self.button_radius = 25
        
        # Round settings
        self.clicks_per_round = 5
        self.current_clicks = 0
        self.round_start_time = None
        self.waiting_for_start = True
        
        # Times history
        self.round_times = []
        self.log_file = os.path.join(os.path.dirname(__file__), "round_times.log")
        self.load_times_from_log()
        
        # Bind space to start round
        self.root.bind("<space>", self.start_round)
        
        # Create UI elements
        self.create_ui()
        
        # Bind window resize to update boundaries
        self.root.bind("<Configure>", self.on_resize)
    
    def on_close(self):
        """Handle window close."""
        print("[DEBUG] Closing window")
        self.root.destroy()
    
    def setup_multi_monitor(self):
        """Detect monitors and calculate window bounds and valid button regions."""
        if HAS_SCREENINFO:
            try:
                monitors = get_monitors()
                if monitors:
                    self.monitors = monitors
                    
                    # Calculate the bounding box of all monitors
                    min_x = min(m.x for m in monitors)
                    min_y = min(m.y for m in monitors)
                    max_x = max(m.x + m.width for m in monitors)
                    max_y = max(m.y + m.height for m in monitors)
                    
                    # Store window position and size (covering all monitors)
                    self.window_x = min_x
                    self.window_y = min_y
                    self.window_width = max_x - min_x
                    self.window_height = max_y - min_y
                    
                    # Store valid screen regions (relative to window position)
                    # These are the actual screen areas where buttons can spawn
                    for m in monitors:
                        region = {
                            'x': m.x - min_x,  # Convert to window-relative coords
                            'y': m.y - min_y,
                            'width': m.width,
                            'height': m.height,
                            'name': m.name if hasattr(m, 'name') else 'Unknown'
                        }
                        self.screen_regions.append(region)
                    
                    print(f"Detected {len(monitors)} monitor(s):")
                    for i, m in enumerate(monitors):
                        print(f"  Monitor {i+1}: {m.width}x{m.height} at ({m.x}, {m.y})")
                    print(f"Window bounds: {self.window_width}x{self.window_height} at ({self.window_x}, {self.window_y})")
                    return
            except Exception as e:
                print(f"Error detecting monitors: {e}")
        
        # Fallback to single monitor mode
        self.root.update_idletasks()
        self.window_x = 0
        self.window_y = 0
        self.window_width = self.root.winfo_screenwidth()
        self.window_height = self.root.winfo_screenheight()
        self.screen_regions = [{
            'x': 0,
            'y': 0,
            'width': self.window_width,
            'height': self.window_height,
            'name': 'Primary'
        }]
        print(f"Single monitor mode: {self.window_width}x{self.window_height}")
    
    def toggle_fullscreen(self, event=None):
        """Toggle between fullscreen and windowed mode."""
        try:
            current = self.root.attributes("-fullscreen")
            self.root.attributes("-fullscreen", not current)
            if current:
                # Going to windowed mode
                self.root.geometry("800x600+100+100")
            print(f"[DEBUG] Fullscreen toggled to: {not current}")
        except Exception as e:
            print(f"Toggle error: {e}")
        
    def create_ui(self):
        """Create all UI elements."""
        # Top frame for info
        self.top_frame = tk.Frame(self.root, bg="#2b2b2b")
        self.top_frame.pack(side=tk.TOP, fill=tk.X, pady=10)
        
        # Status label
        self.status_label = tk.Label(
            self.top_frame,
            text="Press SPACE to start a round",
            font=("Arial", 18, "bold"),
            bg="#2b2b2b",
            fg="#FFD700"
        )
        self.status_label.pack(pady=5)
        
        # Progress label
        self.progress_label = tk.Label(
            self.top_frame,
            text=f"Progress: 0/{self.clicks_per_round}",
            font=("Arial", 14),
            bg="#2b2b2b",
            fg="white"
        )
        self.progress_label.pack(pady=5)
        
        # Times frame on the right side
        self.times_frame = tk.Frame(self.root, bg="#3b3b3b", padx=15, pady=10)
        self.times_frame.place(relx=0.98, rely=0.5, anchor=tk.E)
        
        self.times_title = tk.Label(
            self.times_frame,
            text="Last 10 Times",
            font=("Arial", 12, "bold"),
            bg="#3b3b3b",
            fg="#FFD700"
        )
        self.times_title.pack(pady=(0, 10))
        
        self.times_labels = []
        for i in range(10):
            label = tk.Label(
                self.times_frame,
                text="-",
                font=("Arial", 11),
                bg="#3b3b3b",
                fg="white"
            )
            label.pack(anchor=tk.W)
            self.times_labels.append(label)
        
        self.update_times_display()
        
        # Create canvas for circular button
        self.canvas = tk.Canvas(
            self.root,
            width=self.button_radius * 2 + 4,
            height=self.button_radius * 2 + 4,
            bg="#2b2b2b",
            highlightthickness=0
        )
        
        # Draw circular button
        self.button_id = self.canvas.create_oval(
            2, 2,
            self.button_radius * 2 + 2,
            self.button_radius * 2 + 2,
            fill="#4CAF50",
            outline="#45a049",
            width=3
        )
        
        # Add text to button
        self.button_text = self.canvas.create_text(
            self.button_radius + 2,
            self.button_radius + 2,
            text="GO!",
            font=("Arial", 14, "bold"),
            fill="white"
        )
        
        # Bind click events to the circle
        self.canvas.tag_bind(self.button_id, "<Button-1>", self.on_button_click)
        self.canvas.tag_bind(self.button_text, "<Button-1>", self.on_button_click)
        
        # Hide canvas initially
        self.canvas.place_forget()
        
    def load_times_from_log(self):
        """Load previous times from log file."""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, "r") as f:
                    lines = f.readlines()
                    for line in lines[-10:]:  # Get last 10 entries
                        parts = line.strip().split(" - ")
                        if len(parts) >= 2:
                            time_str = parts[1].replace("s", "")
                            try:
                                self.round_times.append(float(time_str))
                            except ValueError:
                                pass
            except Exception:
                pass
    
    def log_round_time(self, round_time):
        """Log round time to file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_file, "a") as f:
            f.write(f"{timestamp} - {round_time:.3f}s\n")
    
    def update_times_display(self):
        """Update the times display on screen."""
        recent_times = self.round_times[-10:]
        for i, label in enumerate(self.times_labels):
            if i < len(recent_times):
                idx = len(recent_times) - 1 - i  # Reverse order (newest first)
                label.config(text=f"{i+1}. {recent_times[idx]:.3f}s")
            else:
                label.config(text="-")
    
    def on_resize(self, event):
        """Update window dimensions when resized."""
        if event.widget == self.root:
            self.window_width = event.width
            self.window_height = event.height
    
    def start_round(self, event=None):
        """Start a new round."""
        if not self.waiting_for_start:
            return
        
        self.waiting_for_start = False
        self.current_clicks = 0
        self.round_start_time = time.time()
        
        self.status_label.config(text="GO! Click the button!")
        self.progress_label.config(text=f"Progress: 0/{self.clicks_per_round}")
        
        # Show and position the button
        self.canvas.place(x=self.window_width // 2 - self.button_radius,
                         y=self.window_height // 2 - self.button_radius)
        self.move_button_random()
    
    def on_button_click(self, event=None):
        """Handle button click - increment counter and move button."""
        if self.waiting_for_start:
            return
        
        self.current_clicks += 1
        self.progress_label.config(text=f"Progress: {self.current_clicks}/{self.clicks_per_round}")
        
        if self.current_clicks >= self.clicks_per_round:
            self.end_round()
        else:
            self.move_button_random()
    
    def end_round(self):
        """End the current round and show results."""
        round_time = time.time() - self.round_start_time
        self.round_times.append(round_time)
        self.log_round_time(round_time)
        
        self.waiting_for_start = True
        self.canvas.place_forget()
        
        self.status_label.config(text=f"Round complete! Time: {round_time:.3f}s - Press SPACE for next round")
        self.update_times_display()
    
    def move_button_random(self):
        """Move the button to a random position within valid screen regions."""
        margin = 20
        button_size = self.button_radius * 2
        ui_top_margin = 120  # Space for top UI elements
        ui_right_margin = 200  # Space for times panel
        
        # Collect all valid spawn points from actual screen regions
        valid_positions = []
        
        for region in self.screen_regions:
            # Calculate valid bounds within this screen region
            min_x = region['x'] + margin
            min_y = region['y'] + max(margin, ui_top_margin)  # Account for top UI
            max_x = region['x'] + region['width'] - button_size - margin
            max_y = region['y'] + region['height'] - button_size - margin
            
            # For the rightmost part of the rightmost screen, account for times panel
            # Check if this region extends to the right edge of all screens
            region_right_edge = region['x'] + region['width']
            total_right_edge = max(r['x'] + r['width'] for r in self.screen_regions)
            if region_right_edge >= total_right_edge - 10:  # This region is at the right edge
                max_x = max_x - ui_right_margin
            
            if max_x > min_x and max_y > min_y:
                valid_positions.append({
                    'min_x': min_x,
                    'max_x': max_x,
                    'min_y': min_y,
                    'max_y': max_y,
                    'weight': (max_x - min_x) * (max_y - min_y)  # Area-based weight
                })
        
        if not valid_positions:
            # Fallback: use center of first screen region
            region = self.screen_regions[0] if self.screen_regions else {'x': 0, 'y': 0, 'width': 800, 'height': 600}
            new_x = region['x'] + region['width'] // 2 - self.button_radius
            new_y = region['y'] + region['height'] // 2 - self.button_radius
        else:
            # Weight selection by screen area for fair distribution
            total_weight = sum(p['weight'] for p in valid_positions)
            r = random.uniform(0, total_weight)
            cumulative = 0
            selected = valid_positions[0]
            for pos in valid_positions:
                cumulative += pos['weight']
                if r <= cumulative:
                    selected = pos
                    break
            
            new_x = random.randint(int(selected['min_x']), int(selected['max_x']))
            new_y = random.randint(int(selected['min_y']), int(selected['max_y']))
        
        self.canvas.place(x=new_x, y=new_y)
    
    def run(self):
        """Start the application."""
        self.root.mainloop()


if __name__ == "__main__":
    trainer = MouseTrainer()
    trainer.run()
