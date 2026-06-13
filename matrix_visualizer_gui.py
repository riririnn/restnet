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
        # -------------------------------------------------------------------------
        # スライス文字列の意味について (例: '0,0,:,:')
        # -------------------------------------------------------------------------
        # CNNの重みパラメータは通常4次元 (出力チャネル数, 入力チャネル数, カーネル縦, カーネル横) です。
        # 例: embed.conv.weight の Shape が [256, 362, 3, 3] の場合
        # - 第1要素 (256): 256種類の抽出したい特徴パターンのインデックス（出力チャネル数）
        # - 第2要素 (362): 362種類の入力特徴量のインデックス（入力チャネル数）
        #   ※PyTorchのConv2dの仕様では、第1要素が出力(256)、第2要素が入力(362)の順になります。
        # - 第3, 4要素 (3, 3): 3x3の局所的な空間フィルター(小窓)
        #
        # 【なぜ 9x9 のヒートマップではないのか？】
        # AIは「9x9の盤面全体を1つの巨大な重みで見る」のではなく、画像認識で一般的な
        # 「畳み込みニューラルネットワーク(CNN)」を使用しています。
        # 3x3の小さな小窓（フィルター）を盤面上でスライドさせながら局所的なパターン
        # （例：ある駒の隣にどの駒があるか）を探す仕組みになっているため、
        # 保存されている重みのサイズは盤面サイズ(9x9)ではなく、フィルターサイズ(3x3)になります。
        #
        # したがって、'0,0,:,:' は「0番目の出力パターンの、0番目の入力特徴量に対する3x3の重み」を切り出しています。
        # -------------------------------------------------------------------------
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
        # -------------------------------------------------------------------------
        # ヒートマップの可視化の意味について
        # -------------------------------------------------------------------------
        # このヒートマップは盤面の状態ではなく、「AIが盤面を見るためのフィルター（重み）」を表します。
        # CNNの重みを可視化した場合（3x3など）の各要素の意味は以下の通りです：
        #
        # - 縦軸・横軸 (Row Index / Column Index):
        #   盤面全体の座標ではなく、3x3などのフィルター内の局所的な座標 (0,1,2) を表します。
        # 
        # - 色の意味 (色の濃淡):
        #   AIがその局所的な位置にある特徴に対して「どれくらい強く反応するか」を表す係数(重み)です。
        #   * 明るい色 (黄色など) : 正の大きな値。その特徴があるとプラスに評価し強く反応する。
        #   * 暗い色 (紫・紺など) : 負の大きな値。その特徴があるとマイナスに評価し抑制する。
        #   * 中間色 (緑など)     : ゼロに近い値。その特徴をあまり気にしていない。
        # -------------------------------------------------------------------------
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
