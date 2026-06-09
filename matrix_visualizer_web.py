import os
import numpy as np
import matplotlib.pyplot as plt
import gradio as gr

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

def list_files(dir_path):
    if not os.path.isdir(dir_path):
        return gr.update(choices=[], visible=False), "Invalid directory path."
    
    valid_exts = ('.pt', '.pth', '.pkl', '.npy', '.csv', '.txt')
    files = [f for f in os.listdir(dir_path) if f.lower().endswith(valid_exts)]
    files.sort()
    
    if not files:
        return gr.update(choices=[], visible=False), f"No valid files found in {dir_path}"
    
    full_paths = [os.path.join(dir_path, f) for f in files]
    return gr.update(choices=full_paths, value=full_paths[0], visible=True), f"Found {len(files)} files."

def load_data(file_path):
    if not file_path or not os.path.isfile(file_path):
        return None, gr.update(choices=[], visible=False), "No file selected."
    
    ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if ext == '.npy':
            data = np.load(file_path, allow_pickle=True)
        elif ext in ['.csv', '.txt']:
            data = np.loadtxt(file_path, delimiter=',')
        elif ext in ['.pt', '.pth', '.pkl']:
            if not HAS_TORCH:
                return None, gr.update(choices=[], visible=False), "PyTorch is not installed."
            try:
                data = torch.load(file_path, map_location='cpu', weights_only=False)
            except Exception:
                # Fallback for strict environments or specific TorchScript versions
                data = torch.jit.load(file_path, map_location='cpu')
                
            if hasattr(data, 'state_dict'):
                data = data.state_dict()
            
            # もしモデルの重みが 'network' や 'state_dict' というキーの奥にある場合の対応
            if isinstance(data, dict):
                if 'network' in data and isinstance(data['network'], dict):
                    data = data['network']
                elif 'state_dict' in data and isinstance(data['state_dict'], dict):
                    data = data['state_dict']
                    
        else:
            return None, gr.update(choices=[], visible=False), "Unsupported file format."
            
        if isinstance(data, dict):
            keys = list(data.keys())
            if not keys:
                return data, gr.update(choices=[], visible=False), "Dictionary is empty."
            return data, gr.update(choices=keys, value=keys[0], visible=True), f"Loaded dictionary with {len(keys)} keys."
        else:
            return data, gr.update(choices=[], visible=False), f"Loaded array/tensor of shape {get_shape(data)}"
    except Exception as e:
        return None, gr.update(choices=[], visible=False), f"Error loading file: {e}"

def get_shape(val):
    if HAS_TORCH and isinstance(val, torch.Tensor):
        return tuple(val.shape)
    elif isinstance(val, np.ndarray):
        return val.shape
    return "Unknown"

def process_and_plot(data, key, slice_str):
    if data is None:
        return None, "No data loaded.", gr.update(visible=False)
        
    val = data
    if isinstance(data, dict):
        if not key or key not in data:
            return None, "Invalid key selected.", gr.update(visible=False)
        val = data[key]
        
    if HAS_TORCH and isinstance(val, torch.Tensor):
        val = val.detach().numpy()
        
    if not isinstance(val, np.ndarray):
        # テンソルでもNumPy配列でもない場合（例: int, float, stringなど）
        return None, f"Selected data is {type(val)}, not a matrix.", gr.update(visible=False)
        
    info_text = f"Original Shape: {val.shape}"
    
    if val.ndim > 2:
        slice_visible = True
        try:
            if not slice_str:
                slices = [0] * (val.ndim - 2) + [slice(None), slice(None)]
                slice_str = ",".join(["0"] * (val.ndim - 2) + [":", ":"])
            else:
                slices = []
                for s in slice_str.split(','):
                    s = s.strip()
                    if s == ':':
                        slices.append(slice(None))
                    else:
                        slices.append(int(s))
            val = val[tuple(slices)]
            info_text += f" -> Sliced Shape: {val.shape}"
        except Exception as e:
            return None, f"Slice error: {e}", gr.update(visible=True, value=slice_str)
    elif val.ndim == 1:
        val = val[np.newaxis, :]
        info_text += f" -> Expanded Shape: {val.shape}"
        slice_visible = False
    elif val.ndim == 2:
        slice_visible = False
    else:
        return None, "Cannot visualize scalar.", gr.update(visible=False)
        
    if val.ndim != 2:
        return None, f"After slicing, array is {val.ndim}D. Must be 2D.", gr.update(visible=slice_visible)
        
    fig, ax = plt.subplots(figsize=(8, 6))
    cax = ax.imshow(val, cmap='viridis', aspect='auto')
    fig.colorbar(cax, ax=ax)
    ax.set_title(f"Matrix Heatmap ({key if isinstance(data, dict) else 'Array'})\n{info_text}")
    ax.set_xlabel("Column Index")
    ax.set_ylabel("Row Index")
    plt.tight_layout()
    
    return fig, info_text, gr.update(visible=slice_visible, value=slice_str)

with gr.Blocks(title="Matrix Parameter Visualizer") as app:
    gr.Markdown("# Matrix Parameter Visualizer")
    
    data_state = gr.State(None)
    
    with gr.Row():
        # ホストマシンの /home/rin/restnet はコンテナの /workspace にマウントされているためデフォルトパスを調整
        dir_input = gr.Textbox(label="Directory Path", value="/workspace/shogi_9x9_gaz_2R1T2R1T_P_TV_n10/model")
        btn_search = gr.Button("Search Files")
        
    with gr.Row():
        file_dropdown = gr.Dropdown(label="Select File", visible=False, interactive=True)
        
    with gr.Row():
        key_dropdown = gr.Dropdown(label="Select Dictionary Key (Network Layer)", visible=False)
        slice_input = gr.Textbox(label="Slice String (e.g. 0,:,:)", visible=False, info="For >2D tensors")
        
    info_output = gr.Textbox(label="Status / Info", interactive=False)
    plot_output = gr.Plot(label="Heatmap")
    
    # Event wiring
    btn_search.click(
        fn=list_files,
        inputs=[dir_input],
        outputs=[file_dropdown, info_output]
    )
    
    file_dropdown.change(
        fn=load_data,
        inputs=[file_dropdown],
        outputs=[data_state, key_dropdown, info_output]
    ).then(
        fn=process_and_plot,
        inputs=[data_state, key_dropdown, slice_input],
        outputs=[plot_output, info_output, slice_input]
    )
    
    key_dropdown.change(
        fn=process_and_plot,
        inputs=[data_state, key_dropdown, slice_input],
        outputs=[plot_output, info_output, slice_input]
    )
    
    slice_input.submit(
        fn=process_and_plot,
        inputs=[data_state, key_dropdown, slice_input],
        outputs=[plot_output, info_output, slice_input]
    )

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860)
