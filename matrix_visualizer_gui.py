import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import os

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

class MatrixVisualizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Matrix Parameter Visualizer")
        self.root.geometry("800x600")

        self.data = None
        self.current_matrix = None

        # --- Top Frame for Controls ---
        top_frame = tk.Frame(root)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        self.btn_load = tk.Button(top_frame, text="Load File (.npy, .csv, .pt)", command=self.load_file)
        self.btn_load.pack(side=tk.LEFT, padx=5)

        self.lbl_info = tk.Label(top_frame, text="No file loaded.")
        self.lbl_info.pack(side=tk.LEFT, padx=10)

        # Dropdown for dictionary keys (useful for .pt files)
        self.key_var = tk.StringVar()
        self.combo_keys = ttk.Combobox(top_frame, textvariable=self.key_var, state="readonly")
        self.combo_keys.bind("<<ComboboxSelected>>", self.on_key_select)
        self.combo_keys.pack(side=tk.LEFT, padx=5)
        self.combo_keys.pack_forget() # Hide initially

        # Spinboxes for multidimensional array slicing
        self.slice_frame = tk.Frame(top_frame)
        self.slice_frame.pack(side=tk.LEFT, padx=5)
        self.lbl_slice = tk.Label(self.slice_frame, text="Slice (for >2D):")
        self.lbl_slice.pack(side=tk.LEFT)
        self.entry_slice = tk.Entry(self.slice_frame, width=10)
        self.entry_slice.pack(side=tk.LEFT, padx=5)
        self.btn_slice = tk.Button(self.slice_frame, text="Apply", command=self.apply_slice)
        self.btn_slice.pack(side=tk.LEFT)
        self.slice_frame.pack_forget()

        # --- Main Frame for Plot ---
        self.fig, self.ax = plt.subplots(figsize=(6, 5))
        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack(side=tk.BOTH, fill=tk.BOTH, expand=True)

    def load_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Numpy/CSV/PyTorch files", "*.npy *.csv *.txt *.pt *.pth"), ("All files", "*.*")]
        )
        if not file_path:
            return

        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext == '.npy':
                self.data = np.load(file_path, allow_pickle=True)
                self.handle_loaded_data(file_path)
            elif ext in ['.csv', '.txt']:
                self.data = np.loadtxt(file_path, delimiter=',')
                self.handle_loaded_data(file_path)
            elif ext in ['.pt', '.pth', '.pkl']:
                if not HAS_TORCH:
                    messagebox.showerror("Error", "PyTorch is not installed. Cannot load PyTorch files.")
                    return
                try:
                    self.data = torch.load(file_path, map_location='cpu', weights_only=False)
                except Exception:
                    self.data = torch.jit.load(file_path, map_location='cpu')
                
                if hasattr(self.data, 'state_dict'):
                    self.data = self.data.state_dict()
                    
                self.handle_loaded_data(file_path)
            else:
                messagebox.showerror("Error", "Unsupported file format.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file:\n{e}")

    def handle_loaded_data(self, file_path):
        self.lbl_info.config(text=f"Loaded: {os.path.basename(file_path)}")
        self.combo_keys.pack_forget()
        self.slice_frame.pack_forget()

        if isinstance(self.data, dict):
            # It's a dictionary (likely a PyTorch state_dict)
            keys = list(self.data.keys())
            if not keys:
                messagebox.showwarning("Warning", "The dictionary is empty.")
                return
            self.combo_keys['values'] = keys
            self.combo_keys.current(0)
            self.combo_keys.pack(side=tk.LEFT, padx=5)
            self.on_key_select(None)
        else:
            self.set_matrix_and_plot(self.data)

    def on_key_select(self, event):
        key = self.key_var.get()
        if not key:
            return
        val = self.data[key]
        self.set_matrix_and_plot(val)

    def set_matrix_and_plot(self, val):
        if HAS_TORCH and isinstance(val, torch.Tensor):
            val = val.detach().numpy()
        
        if not isinstance(val, np.ndarray):
            messagebox.showwarning("Warning", f"Selected data is of type {type(val)}, not a matrix.")
            self.ax.clear()
            self.canvas.draw()
            return

        self.current_matrix = val

        if val.ndim > 2:
            self.slice_frame.pack(side=tk.LEFT, padx=5)
            # Default slice to 0 for extra dimensions
            default_slice = ','.join(['0'] * (val.ndim - 2)) + ',:,:'
            self.entry_slice.delete(0, tk.END)
            self.entry_slice.insert(0, default_slice)
            self.lbl_info.config(text=f"Shape: {val.shape} (Applying slice)")
            self.apply_slice()
        elif val.ndim == 2:
            self.slice_frame.pack_forget()
            self.lbl_info.config(text=f"Shape: {val.shape}")
            self.plot_matrix(val)
        elif val.ndim == 1:
            self.slice_frame.pack_forget()
            self.lbl_info.config(text=f"Shape: {val.shape}")
            # Expand to 2D for visualization
            self.plot_matrix(val[np.newaxis, :])
        else:
            messagebox.showwarning("Warning", "Scalar value cannot be visualized as a matrix.")

    def apply_slice(self):
        slice_str = self.entry_slice.get()
        try:
            # Safely evaluate slice string. E.g., '0,0,:,:'
            slices = []
            for s in slice_str.split(','):
                s = s.strip()
                if s == ':':
                    slices.append(slice(None))
                else:
                    slices.append(int(s))
            
            sliced_mat = self.current_matrix[tuple(slices)]
            if sliced_mat.ndim != 2:
                messagebox.showerror("Error", f"Slice resulted in {sliced_mat.ndim}D array. Please specify a 2D slice.")
                return
            self.plot_matrix(sliced_mat)
        except Exception as e:
            messagebox.showerror("Error", f"Invalid slice format. Use format like '0,:,:'\n{e}")

    def plot_matrix(self, mat):
        self.ax.clear()
        cax = self.ax.imshow(mat, cmap='viridis', aspect='auto')
        
        # Add colorbar if not present
        if not hasattr(self, 'colorbar'):
            self.colorbar = self.fig.colorbar(cax, ax=self.ax)
        else:
            self.colorbar.update_normal(cax)
            
        self.ax.set_title("Matrix Heatmap")
        self.ax.set_xlabel("Column Index")
        self.ax.set_ylabel("Row Index")
        self.fig.tight_layout()
        self.canvas.draw()

if __name__ == "__main__":
    root = tk.Tk()
    app = MatrixVisualizerApp(root)
    root.mainloop()
