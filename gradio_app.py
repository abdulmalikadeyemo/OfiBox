import os
import random
import shutil
import time
import uuid
from pathlib import Path
import base64
from io import BytesIO
import threading

import gradio as gr
import requests
from PIL import Image
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

API_URL = 'http://184.105.4.15:8081'

# Configuration
APP_CONFIG = {
    # Gradio app settings
    'host': '0.0.0.0',
    'port': 8080,
    
    # API server settings
    'api_url': API_URL,  # Replace with your Paperspace public IP
    
    # UI settings
    'title': 'OfiBox Game Asset Generator: Create High-Quality 3D Game Assets',
    
    # Cache settings
    'cache_dir': 'gradio_cache',
    'max_cache_folders': 200,
}

# Constants
MAX_SEED = int(1e7)
SAVE_DIR = APP_CONFIG['cache_dir']
os.makedirs(SAVE_DIR, exist_ok=True)

# Model viewer constants and functions
HTML_HEIGHT = 650
HTML_WIDTH = 500
HTML_OUTPUT_PLACEHOLDER = f"""
<div style='height: {650}px; width: 100%; border-radius: 8px; border-color: #e5e7eb; border-style: solid; border-width: 1px; display: flex; justify-content: center; align-items: center;'>
  <div style='text-align: center; font-size: 16px; color: #6b7280;'>
    <p style="color: #8d8d8d;">Welcome to OfiBox Game Asset Generator!</p>
    <p style="color: #8d8d8d;">Create amazing 3D assets for your games.</p>
  </div>
</div>
"""

class APIStatus:
    CONNECTED = "🟢 Connected"
    DISCONNECTED = "🔴 Disconnected"
    BUSY = "🟡 Busy"

class OfiBoxAPIClient:
    def __init__(self, api_url=API_URL):
        self.api_url = api_url.rstrip('/')
        self._status = APIStatus.DISCONNECTED
        self._status_lock = threading.Lock()
        self._start_status_checker()
        
    @property
    def status(self):
        with self._status_lock:
            return self._status
            
    @status.setter
    def status(self, value):
        with self._status_lock:
            self._status = value
    
    def _start_status_checker(self):
        """Start a background thread to check API status"""
        def check_status():
            while True:
                try:
                    response = requests.get(f"{self.api_url}/health", timeout=2)
                    if response.status_code == 200:
                        self.status = APIStatus.CONNECTED
                    else:
                        self.status = APIStatus.DISCONNECTED
                except:
                    self.status = APIStatus.DISCONNECTED
                time.sleep(5)  # Check every 5 seconds
                
        thread = threading.Thread(target=check_status, daemon=True)
        thread.start()
        
    def _encode_image(self, image):
        """Convert PIL Image to base64 string"""
        if isinstance(image, str):  # If it's a file path
            with open(image, 'rb') as f:
                return base64.b64encode(f.read()).decode()
        
        # If it's a PIL Image
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()

    def generate(self, image=None, text=None, params=None):
        """Synchronous generation request"""
        if self.status != APIStatus.CONNECTED:
            raise ConnectionError("Generation server is not available. Please try again later or contact support.")
            
        if params is None:
            params = {}
            
        if image:
            params["image"] = self._encode_image(image)
        elif text:
            params["text"] = text
        else:
            raise ValueError("Please provide either a reference image or a text description.")

        try:
            self.status = APIStatus.BUSY
            response = requests.post(f"{self.api_url}/generate", json=params, timeout=30)
            response.raise_for_status()
            
            # Save the response content to a temporary file
            save_folder = self._gen_save_folder()
            output_path = os.path.join(save_folder, "output.glb")
            with open(output_path, "wb") as f:
                f.write(response.content)
            return output_path
            
        except requests.exceptions.Timeout:
            raise ConnectionError("Generation is taking longer than expected. Please try again with simpler parameters.")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Unable to connect to generation server. Please try again later.")
        finally:
            if self.status == APIStatus.BUSY:
                self.status = APIStatus.CONNECTED

    def send_async(self, image=None, text=None, params=None):
        """Asynchronous generation request"""
        if params is None:
            params = {}
            
        if image:
            params["image"] = self._encode_image(image)
        elif text:
            params["text"] = text
        else:
            raise ValueError("Either image or text must be provided")

        try:
            response = requests.post(f"{self.api_url}/send", json=params)
            response.raise_for_status()
            return response.json()["uid"]
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Failed to connect to API server: {str(e)}")

    def check_status(self, uid):
        """Check status of asynchronous generation"""
        try:
            response = requests.get(f"{self.api_url}/status/{uid}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Failed to connect to API server: {str(e)}")

    def _gen_save_folder(self, max_size=200):
        """Generate a unique folder for saving outputs"""
        os.makedirs(SAVE_DIR, exist_ok=True)
        
        # Get all folder paths
        dirs = [f for f in Path(SAVE_DIR).iterdir() if f.is_dir()]
        
        # If folder count exceeds max_size, remove oldest folder
        if len(dirs) >= max_size:
            oldest_dir = min(dirs, key=lambda x: x.stat().st_ctime)
            shutil.rmtree(oldest_dir)
            
        # Generate new uuid folder name
        new_folder = os.path.join(SAVE_DIR, str(uuid.uuid4()))
        os.makedirs(new_folder, exist_ok=True)
        
        return new_folder

# Helper functions for the Gradio interface
def get_example_img_list():
    """Load example images from assets"""
    print('Loading example img list ...')
    try:
        from glob import glob
        return sorted(glob('./assets/example_images/**/*.png', recursive=True))
    except Exception:
        print("Warning: No example images found")
        return []

def get_example_txt_list():
    """Load example prompts from assets"""
    print('Loading example txt list ...')
    txt_list = []
    try:
        with open('./assets/example_prompts.txt', encoding='utf-8') as f:
            for line in f:
                txt_list.append(line.strip())
    except FileNotFoundError:
        print("Warning: example_prompts.txt not found")
    return txt_list

def randomize_seed_fn(seed: int, randomize_seed: bool) -> int:
    """Generate random seed if randomize_seed is True"""
    if randomize_seed:
        seed = random.randint(0, MAX_SEED)
    return seed 

def generation_all(
    api_client,
    api_status,
    caption=None,
    image=None,
    steps=50,
    guidance_scale=7.5,
    seed=1234,
    octree_resolution=256,
    check_box_rembg=False,
    num_chunks=200000,
    randomize_seed: bool = False,
):
    """Generate both untextured and textured 3D models"""
    seed = int(randomize_seed_fn(seed, randomize_seed))
    
    # Prepare parameters
    params = {
        "steps": steps,
        "guidance_scale": guidance_scale,
        "seed": seed,
        "octree_resolution": octree_resolution,
        "check_box_rembg": check_box_rembg,
        "num_chunks": num_chunks,
        "texture": True
    }
    
    try:
        output_path = api_client.generate(image=image, text=caption, params=params)
        save_folder = os.path.dirname(output_path)
        
        model_viewer_html = build_model_viewer_html(save_folder, height=HTML_HEIGHT, width=HTML_WIDTH, textured=True)
        
        return (
            gr.update(value=output_path),
            model_viewer_html,
            {
                "Asset Details": {
                    "Quality Level": steps,
                    "Style Intensity": guidance_scale,
                    "Generation ID": seed,
                    "Resolution": octree_resolution,
                    "Detail Level": num_chunks,
                }
            },
            seed,
            api_client.status,
        )
    except Exception as e:
        error_html = f"""
        <div style='height: {HTML_HEIGHT}px; width: 100%; display: flex; justify-content: center; align-items: center; background-color: #FEF2F2; border-radius: 8px;'>
            <div style='text-align: center; color: #DC2626;'>
                <p style='font-size: 1.2em; margin-bottom: 10px;'>⚠️ Generation Failed</p>
                <p>We couldn't generate your asset: {str(e)}</p>
                <p style='font-size: 0.9em; margin-top: 10px;'>Try adjusting the generation settings or using a different reference.</p>
            </div>
        </div>
        """
        return (
            gr.update(value=None),
            error_html,
            {"error": "Asset generation failed. Please try again with different settings."},
            seed,
            api_client.status,
        )

def shape_generation(
    api_client,
    api_status,
    caption=None,
    image=None,
    steps=50,
    guidance_scale=7.5,
    seed=1234,
    octree_resolution=256,
    check_box_rembg=False,
    num_chunks=200000,
    randomize_seed: bool = False,
):
    """Generate untextured 3D model only"""
    seed = int(randomize_seed_fn(seed, randomize_seed))
    
    # Prepare parameters
    params = {
        "steps": steps,
        "guidance_scale": guidance_scale,
        "seed": seed,
        "octree_resolution": octree_resolution,
        "check_box_rembg": check_box_rembg,
        "num_chunks": num_chunks,
        "texture": False  # Request untextured output
    }
    
    try:
        # Make API request
        output_path = api_client.generate(image=image, text=caption, params=params)
        save_folder = os.path.dirname(output_path)
        
        # Generate HTML for model viewer
        model_viewer_html = build_model_viewer_html(save_folder, height=HTML_HEIGHT, width=HTML_WIDTH)
        
        # Return results
        return (
            gr.update(value=output_path),  # File output
            model_viewer_html,  # HTML viewer
            {"params": params},  # Stats
            seed,  # Updated seed
            api_client.status,  # API status
        )
    except Exception as e:
        error_html = f"""
        <div style='height: {HTML_HEIGHT}px; width: 100%; display: flex; justify-content: center; align-items: center; background-color: #FEF2F2; border-radius: 8px;'>
            <div style='text-align: center; color: #DC2626;'>
                <p style='font-size: 1.2em; margin-bottom: 10px;'>⚠️ Generation Failed</p>
                <p>{str(e)}</p>
            </div>
        </div>
        """
        return (
            gr.update(value=None),
            error_html,
            {"error": str(e)},
            seed,
            api_client.status,
        )

def build_model_viewer_html(save_folder, height=660, width=790, textured=False):
    """Build HTML for the model viewer"""
    if textured:
        related_path = f"./textured_mesh.glb"
        template_name = './assets/modelviewer-textured-template.html'
        output_html_path = os.path.join(save_folder, f'textured_mesh.html')
    else:
        related_path = f"./output.glb"
        template_name = './assets/modelviewer-template.html'
        output_html_path = os.path.join(save_folder, f'white_mesh.html')
    
    offset = 50 if textured else 10
    
    try:
        with open(os.path.join(os.path.dirname(__file__), template_name), 'r', encoding='utf-8') as f:
            template_html = f.read()

        with open(output_html_path, 'w', encoding='utf-8') as f:
            template_html = template_html.replace('#height#', f'{height - offset}')
            template_html = template_html.replace('#width#', f'{width}')
            template_html = template_html.replace('#src#', f'{related_path}/')
            f.write(template_html)

        rel_path = os.path.relpath(output_html_path, SAVE_DIR)
        iframe_tag = f'<iframe src="/static/{rel_path}" height="{height}" width="100%" frameborder="0"></iframe>'
        
        return f"""
            <div style='height: {height}; width: 100%;'>
            {iframe_tag}
            </div>
        """
    except FileNotFoundError:
        return f"""
            <div style='height: {height}px; width: 100%; display: flex; justify-content: center; align-items: center;'>
                <div style='text-align: center; color: red;'>
                    Error: Model viewer template not found. Please ensure the assets directory is present.
                </div>
            </div>
        """

def build_app():
    """Build the Gradio interface"""
    # Initialize API client
    api_client = OfiBoxAPIClient(APP_CONFIG['api_url'])
    
    # Custom CSS
    custom_css = """
    .app.svelte-wpkpf6.svelte-wpkpf6:not(.fill_width) {
        max-width: 1480px;
    }
    .api-status {
        text-align: center;
        padding: 5px;
        border-radius: 4px;
        margin: 5px 0;
    }
    """

    with gr.Blocks(
        theme=gr.themes.Base(),
        title='OfiBox Game Asset Generator',
        analytics_enabled=False,
        css=custom_css
    ) as demo:
        title_html = f"""
        <div style="font-size: 2em; font-weight: bold; text-align: center; margin-bottom: 5px">
        {APP_CONFIG['title']}
        </div>
        """
        gr.HTML(title_html)
        
        # API Status indicator
        api_status = gr.Textbox(
            value=api_client.status,
            label="Server Status",
            interactive=False,
            container=False,
            elem_classes=["api-status"]
        )
        
        gr.HTML(f"""
        <div align="center">
        OfiBox Game Asset Generator - Powered by Advanced AI Technology
        </div>
        """)

        with gr.Row():
            with gr.Column(scale=3):
                with gr.Tabs() as tabs_prompt:
                    with gr.Tab('Image Reference', id='tab_img_prompt'):
                        image = gr.Image(label='Reference Image', type='pil', image_mode='RGBA', height=290)

                    with gr.Tab('Text Description', id='tab_txt_prompt'):
                        caption = gr.Textbox(
                            label='Asset Description',
                            placeholder='Describe the game asset you want to create',
                            info='Example: A low-poly treasure chest with golden details and rustic wood texture'
                        )

                with gr.Row():
                    btn = gr.Button(value='Generate Base Model', variant='primary', min_width=100)
                    btn_all = gr.Button(value='Generate Textured Model', variant='primary', min_width=100)

                with gr.Group():
                    file_out = gr.File(label="Generated Asset", visible=False)

                with gr.Tabs():
                    with gr.Tab('Generation Settings', id='tab_advanced_options'):
                        with gr.Row():
                            check_box_rembg = gr.Checkbox(value=True, label='Remove Background', min_width=100)
                            randomize_seed = gr.Checkbox(label="Randomize Generation", value=True, min_width=100)
                        seed = gr.Slider(
                            label="Generation Seed",
                            minimum=0,
                            maximum=MAX_SEED,
                            step=1,
                            value=1234,
                            min_width=100,
                        )
                        with gr.Row():
                            num_steps = gr.Slider(maximum=100,
                                                minimum=1,
                                                value=30,
                                                step=1,
                                                label='Quality Steps')
                            octree_resolution = gr.Slider(maximum=512,
                                                        minimum=16,
                                                        value=256,
                                                        label='Model Resolution')
                        with gr.Row():
                            cfg_scale = gr.Number(value=5.0,
                                                label='Style Strength',
                                                min_width=100)
                            num_chunks = gr.Slider(maximum=5000000,
                                                minimum=1000,
                                                value=8000,
                                                label='Detail Level',
                                                min_width=100)

            with gr.Column(scale=6):
                with gr.Tabs() as tabs_output:
                    with gr.Tab('Generated Asset Preview', id='gen_mesh_panel'):
                        html_gen_mesh = gr.HTML(HTML_OUTPUT_PLACEHOLDER, label='3D Preview')
                    with gr.Tab('Asset Information', id='stats_panel'):
                        stats = gr.JSON({}, label='Generation Stats')

            with gr.Column(scale=2):
                with gr.Tabs() as gallery:
                    with gr.Tab('Reference Gallery', id='tab_img_gallery'):
                        with gr.Row():
                            gr.Examples(
                                examples=get_example_img_list(),
                                inputs=[image],
                                label=None,
                                examples_per_page=18
                            )

                    with gr.Tab('Example Descriptions', id='tab_txt_gallery'):
                        with gr.Row():
                            gr.Examples(
                                examples=get_example_txt_list(),
                                inputs=[caption],
                                label=None,
                                examples_per_page=18
                            )

        # Set up event handlers
        btn.click(
            fn=lambda *args: shape_generation(api_client, *args),
            inputs=[
                api_status,
                caption,
                image,
                num_steps,
                cfg_scale,
                seed,
                octree_resolution,
                check_box_rembg,
                num_chunks,
                randomize_seed,
            ],
            outputs=[file_out, html_gen_mesh, stats, seed, api_status]
        )

        btn_all.click(
            fn=lambda *args: generation_all(api_client, *args),
            inputs=[
                api_status,
                caption,
                image,
                num_steps,
                cfg_scale,
                seed,
                octree_resolution,
                check_box_rembg,
                num_chunks,
                randomize_seed,
            ],
            outputs=[file_out, html_gen_mesh, stats, seed, api_status]
        )

        # Update API status periodically
        api_status.change(None, [], [])  # This creates a dummy event loop
        demo.load(lambda: api_client.status, outputs=[api_status])

    return demo

if __name__ == "__main__":
    # Create FastAPI app
    app = FastAPI()
    
    # Mount static directory for model viewer
    static_dir = Path(SAVE_DIR).absolute()
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir, html=True), name="static")
    
    # Copy environment maps if they exist
    env_maps_src = './assets/env_maps'
    env_maps_dst = os.path.join(static_dir, 'env_maps')
    if os.path.exists(env_maps_src):
        shutil.copytree(env_maps_src, env_maps_dst, dirs_exist_ok=True)
    
    # Build and mount Gradio app
    demo = build_app()
    app = gr.mount_gradio_app(app, demo, path="/")
    
    # Run the server
    uvicorn.run(app, host=APP_CONFIG['host'], port=APP_CONFIG['port']) 