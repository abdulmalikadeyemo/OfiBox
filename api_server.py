#///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////# Hunyuan 3D is licensed under the TENCENT HUNYUAN NON-COMMERCIAL LICENSE AGREEMENT
# except for the third-party components listed below.////////////////////
# Hunyuan 3D does not impose any additional limitations beyond what is outlined
# in the repsective licenses of these third-party components.
# Users must comply with all terms and conditions of original licenses of these third-party
# components and must ensure that the usage of the third party components adheres to
# all relevant laws and regulations.

# For avoidance of doubts, Hunyuan 3D means the large language models and
# their software and algorithms, including trained model weights, parameters (including
# optimizer states), machine-learning model code, inference-enabling code, training-enabling code,
# fine-tuning enabling code and other elements of the foregoing made publicly available
# by Tencent in accordance with TENCENT HUNYUAN COMMUNITY LICENSE AGREEMENT.

"""
A model worker executes the model.
"""
import argparse
import asyncio
import base64
import logging
import logging.handlers
import os
import sys
import tempfile
import threading
import traceback
import uuid
from io import BytesIO
import shutil

import torch
import trimesh
import uvicorn
from PIL import Image
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.websockets import WebSocket, WebSocketDisconnect

from hy3dgen.rembg import BackgroundRemover
from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline, FloaterRemover, DegenerateFaceRemover, FaceReducer, \
    MeshSimplifier
from hy3dgen.texgen import Hunyuan3DPaintPipeline
from hy3dgen.text2image import HunyuanDiTPipeline

LOGDIR = '.'
# Define models directory to store local models
MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
os.makedirs(MODELS_DIR, exist_ok=True)

server_error_msg = "**NETWORK ERROR DUE TO HIGH TRAFFIC. PLEASE REGENERATE OR REFRESH THIS PAGE.**"
moderation_msg = "YOUR INPUT VIOLATES OUR CONTENT MODERATION GUIDELINES. PLEASE TRY AGAIN."

handler = None


def build_logger(logger_name, logger_filename):
    global handler

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Set the format of root handlers
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)
    logging.getLogger().handlers[0].setFormatter(formatter)

    # Redirect stdout and stderr to loggers
    stdout_logger = logging.getLogger("stdout")
    stdout_logger.setLevel(logging.INFO)
    sl = StreamToLogger(stdout_logger, logging.INFO)
    sys.stdout = sl

    stderr_logger = logging.getLogger("stderr")
    stderr_logger.setLevel(logging.ERROR)
    sl = StreamToLogger(stderr_logger, logging.ERROR)
    sys.stderr = sl

    # Get logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    # Add a file handler for all loggers
    if handler is None:
        os.makedirs(LOGDIR, exist_ok=True)
        filename = os.path.join(LOGDIR, logger_filename)
        handler = logging.handlers.TimedRotatingFileHandler(
            filename, when='D', utc=True, encoding='UTF-8')
        handler.setFormatter(formatter)

        for name, item in logging.root.manager.loggerDict.items():
            if isinstance(item, logging.Logger):
                item.addHandler(handler)

    return logger


class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """

    def __init__(self, logger, log_level=logging.INFO):
        self.terminal = sys.stdout
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ''

    def __getattr__(self, attr):
        return getattr(self.terminal, attr)

    def write(self, buf):
        temp_linebuf = self.linebuf + buf
        self.linebuf = ''
        for line in temp_linebuf.splitlines(True):
            # From the io.TextIOWrapper docs:
            #   On output, if newline is None, any '\n' characters written
            #   are translated to the system default line separator.
            # By default sys.stdout.write() expects '\n' newlines and then
            # translates them so this is still cross platform.
            if line[-1] == '\n':
                self.logger.log(self.log_level, line.rstrip())
            else:
                self.linebuf += line

    def flush(self):
        if self.linebuf != '':
            self.logger.log(self.log_level, self.linebuf.rstrip())
        self.linebuf = ''


def pretty_print_semaphore(semaphore):
    if semaphore is None:
        return "None"
    return f"Semaphore(value={semaphore._value}, locked={semaphore.locked()})"


SAVE_DIR = 'gradio_cache'
os.makedirs(SAVE_DIR, exist_ok=True)

worker_id = str(uuid.uuid4())[:6]
logger = build_logger("controller", f"{SAVE_DIR}/controller.log")


def load_image_from_base64(image):
    return Image.open(BytesIO(base64.b64decode(image)))


def ensure_model_exists(model_path, model_type="shape", models_dir=None):
    """
    Ensures that a model exists at the specified path.
    If the model_path is a HuggingFace repo ID, it will download the model if it doesn't exist locally.
    If the model_path is a local path, it will verify the path exists.
    
    Args:
        model_path (str): HuggingFace repo ID or local path
        model_type (str): Type of model ("shape", "texture", or "t2i")
        models_dir (str): Directory to store models
    
    Returns:
        str: The validated model path (either local path or HF repo ID)
    """
    # Default to module-level MODELS_DIR if none provided
    if models_dir is None:
        models_dir = MODELS_DIR
        
    # Check if it's a local path
    if os.path.exists(model_path):
        logger.info(f"Using local model at {model_path}")
        return model_path
    
    # Check if it's a path relative to models_dir
    local_model_path = os.path.join(models_dir, os.path.basename(model_path))
    if os.path.exists(local_model_path):
        logger.info(f"Using local model at {local_model_path}")
        return local_model_path
    
    # It's probably a HuggingFace repo ID, verify it can be downloaded
    # We don't actually download it here, as the HF libraries will handle caching
    # Just log that we're using the remote model
    logger.info(f"Using remote model {model_path} (will be cached by HuggingFace)")
    
    # Set the HF_HOME environment variable to use our custom cache directory
    os.environ['HF_HOME'] = models_dir
    
    return model_path


class ModelWorker:
    def __init__(self,
                 model_path='tencent/Hunyuan3D-2mini',
                 tex_model_path='tencent/Hunyuan3D-2',
                 subfolder='hunyuan3d-dit-v2-mini-turbo',
                 device='cuda',
                 enable_tex=False,
                 enable_t2i=False,
                 models_dir=None):
        self.worker_id = worker_id
        self.device = device
        self.models_dir = models_dir if models_dir else MODELS_DIR
        
        # Validate and ensure model paths exist
        try:
            self.model_path = ensure_model_exists(model_path, "shape", self.models_dir)
            logger.info(f"Loading the model {self.model_path} on worker {worker_id} ...")
            
            self.rembg = BackgroundRemover()
            self.pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
                self.model_path,
                subfolder=subfolder,
                use_safetensors=True,
                device=device,
            )
            self.pipeline.enable_flashvdm(mc_algo='mc')
            
            # Only initialize text-to-image pipeline if explicitly enabled
            if enable_t2i:
                try:
                    t2i_model_path = 'Tencent-Hunyuan/HunyuanDiT-v1.1-Diffusers-Distilled'
                    t2i_model_path = ensure_model_exists(t2i_model_path, "t2i", self.models_dir)
                    from hy3dgen.text2image import HunyuanDiTPipeline
                    self.pipeline_t2i = HunyuanDiTPipeline(
                        t2i_model_path,
                        device=device
                    )
                    logger.info("Text-to-image pipeline initialized successfully")
                    print("Text-to-image pipeline initialized successfully")
                except Exception as e:
                    logger.error(f"Failed to initialize text-to-image pipeline: {e}")
                    # Don't assign pipeline_t2i if initialization fails
            
            if enable_tex:
                tex_model_path = ensure_model_exists(tex_model_path, "texture", self.models_dir)
                self.pipeline_tex = Hunyuan3DPaintPipeline.from_pretrained(tex_model_path)
                logger.info("Texture pipeline initialized successfully")
                print("Texture pipeline initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing model worker: {e}")
            raise

    def get_queue_length(self):
        if model_semaphore is None:
            return 0
        else:
            return args.limit_model_concurrency - model_semaphore._value + (len(
                model_semaphore._waiters) if model_semaphore._waiters is not None else 0)

    def get_status(self):
        return {
            "speed": 1,
            "queue_length": self.get_queue_length(),
        }

    @torch.inference_mode()
    def generate(self, uid, params):
        if 'image' in params:
            image = params["image"]
            image = load_image_from_base64(image)
        else:
            if 'text' in params:
                text = params["text"]
                # Check if text-to-image pipeline is available
                if hasattr(self, 'pipeline_t2i'):
                    image = self.pipeline_t2i(text)
                else:
                    # Text-to-image pipeline not initialized
                    raise ValueError("Text-to-image pipeline not available. Please provide an image instead.")
            else:
                raise ValueError("No input image or text provided")

        image = self.rembg(image)
        params['image'] = image

        if 'mesh' in params:
            mesh = trimesh.load(BytesIO(base64.b64decode(params["mesh"])), file_type='glb')
        else:
            seed = params.get("seed", 1234)
            params['generator'] = torch.Generator(self.device).manual_seed(seed)
            params['octree_resolution'] = params.get("octree_resolution", 128)
            params['num_inference_steps'] = params.get("num_inference_steps", 5)
            params['guidance_scale'] = params.get('guidance_scale', 5.0)
            params['mc_algo'] = 'mc'
            import time
            start_time = time.time()
            mesh = self.pipeline(**params)[0]
            logger.info("--- %s seconds ---" % (time.time() - start_time))

        if params.get('texture', True):
            if hasattr(self, 'pipeline_tex'):
                mesh = FloaterRemover()(mesh)
                mesh = DegenerateFaceRemover()(mesh)
                mesh = FaceReducer()(mesh, max_facenum=params.get('face_count', 40000))
                mesh = self.pipeline_tex(mesh, image)
                print("Texture pipeline applied to mesh successfully")
            else:
                logger.warning("Texture pipeline requested but not initialized")

        type = params.get('type', 'glb')
        with tempfile.NamedTemporaryFile(suffix=f'.{type}', delete=False) as temp_file:
            mesh.export(temp_file.name)
            mesh = trimesh.load(temp_file.name)
            save_path = os.path.join(SAVE_DIR, f'{str(uid)}.{type}')
            mesh.export(save_path)

        torch.cuda.empty_cache()
        return save_path, uid


parser = argparse.ArgumentParser()
parser.add_argument("--host", type=str, default="0.0.0.0")
parser.add_argument("--port", type=int, default=8081)
parser.add_argument("--model_path", type=str, default='tencent/Hunyuan3D-2mini')
parser.add_argument("--tex_model_path", type=str, default='tencent/Hunyuan3D-2')
parser.add_argument("--device", type=str, default="cuda")
parser.add_argument("--limit-model-concurrency", type=int, default=5)
parser.add_argument('--enable_tex', action='store_true', default=True)
parser.add_argument('--enable_t2i', action='store_true', default=True, help='Enable text-to-image pipeline')
parser.add_argument('--subfolder', type=str, default='hunyuan3d-dit-v2-mini-turbo', help='Subfolder for the model')
parser.add_argument('--models_dir', type=str, default=MODELS_DIR, help='Directory to store model cache')
args = parser.parse_args()

# Create models directory from args
models_dir = args.models_dir
os.makedirs(models_dir, exist_ok=True)

# Set HF_HOME for model caching
os.environ['HF_HOME'] = models_dir

logger.info(f"args: {args}")
logger.info(f"Models directory: {models_dir}")
model_semaphore = asyncio.Semaphore(args.limit_model_concurrency)


worker = ModelWorker(
    model_path=args.model_path, 
    device=args.device, 
    enable_tex=args.enable_tex,
    tex_model_path=args.tex_model_path, 
    subfolder=args.subfolder, 
    enable_t2i=args.enable_t2i,
    models_dir=models_dir
)

app = FastAPI()
from fastapi.middleware.cors import CORSMiddleware
from fastapi.websockets import WebSocket, WebSocketDisconnect

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Add a health check endpoint for monitoring and debugging
@app.get("/health")
async def health_check():
    return {
        "status": "ok", 
        "message": "Hunyuan3D API server is running",
        "worker_id": worker_id,
        "version": "2.0.2"
    }

# Add a root endpoint for basic info
@app.get("/")
async def root():
    return {
        "name": "Hunyuan3D-2 API",
        "status": "running",
        "endpoints": [
            {"path": "/health", "method": "GET", "description": "Health check endpoint"},
            {"path": "/generate", "method": "POST", "description": "Generate 3D model from image/text"},
            {"path": "/send", "method": "POST", "description": "Queue generation job"},
            {"path": "/status/{uid}", "method": "GET", "description": "Check status of generation job"}
        ]
    }

# Add WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            uid = uuid.uuid4()
            
            # Process the request similar to /generate endpoint
            try:
                file_path, uid = worker.generate(uid, data)
                # Return the file path as a response
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                    
                await websocket.send_json({
                    "status": "success",
                    "uid": str(uid),
                    "file_path": file_path
                })
            except Exception as e:
                await websocket.send_json({
                    "status": "error",
                    "message": str(e)
                })
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.send_json({
                "status": "error",
                "message": server_error_msg
            })
        except:
            pass

# Simple WebSocket test endpoint
@app.websocket("/ws/test")
async def websocket_test(websocket: WebSocket):
    await websocket.accept()
    try:
        await websocket.send_json({"status": "connected", "message": "WebSocket connection successful"})
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        logger.info("Test WebSocket client disconnected")
    except Exception as e:
        logger.error(f"Test WebSocket error: {str(e)}")

# Original endpoints
@app.post("/generate")
async def generate(request: Request):
    logger.info("Worker generating...")
    params = await request.json()
    uid = uuid.uuid4()
    try:
        file_path, uid = worker.generate(uid, params)
        return FileResponse(file_path)
    except ValueError as e:
        traceback.print_exc()
        print("Caught ValueError:", e)
        ret = {
            "text": server_error_msg,
            "error_code": 1,
        }
        return JSONResponse(ret, status_code=404)
    except torch.cuda.CudaError as e:
        print("Caught torch.cuda.CudaError:", e)
        ret = {
            "text": server_error_msg,
            "error_code": 1,
        }
        return JSONResponse(ret, status_code=404)
    except Exception as e:
        print("Caught Unknown Error", e)
        traceback.print_exc()
        ret = {
            "text": server_error_msg,
            "error_code": 1,
        }
        return JSONResponse(ret, status_code=404)


@app.post("/send")
async def generate(request: Request):
    logger.info("Worker send...")
    params = await request.json()
    uid = uuid.uuid4()
    threading.Thread(target=worker.generate, args=(uid, params,)).start()
    ret = {"uid": str(uid)}
    return JSONResponse(ret, status_code=200)


@app.get("/status/{uid}")
async def status(uid: str):
    save_file_path = os.path.join(SAVE_DIR, f'{uid}.glb')
    print(save_file_path, os.path.exists(save_file_path))
    if not os.path.exists(save_file_path):
        response = {'status': 'processing'}
        return JSONResponse(response, status_code=200)
    else:
        base64_str = base64.b64encode(open(save_file_path, 'rb').read()).decode()
        response = {'status': 'completed', 'model_base64': base64_str}
        return JSONResponse(response, status_code=200)


if __name__ == "__main__":

    try:
        uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)
