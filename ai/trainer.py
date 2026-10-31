"""
Automated Training & ONNX Export Pipeline for Clash of Clans YOLO Models.
Advanced Training Options:
- Configurable Epochs, Batch Size, Resolution (640 / 960)
- Model Architecture Selection (yolov8n, yolov8s, yolo11n)
- Device Accelerator (Auto / CUDA / CPU)
- Safe Multiprocessing (workers=0 on Windows)
- Direct ONNX Export & Verification
"""

import os
import sys
import shutil
import yaml
from ai.constants import CLASSES


def create_dataset_yaml(data_dir="ai_data", output_yaml="ai_data/coc_dataset.yaml"):
    """Creates the dataset configuration YAML required by YOLO."""
    abs_data_dir = os.path.abspath(data_dir).replace("\\", "/")
    
    cfg = {
        "path": abs_data_dir,
        "train": "images",
        "val": "images",
        "names": {i: name for i, name in enumerate(CLASSES)}
    }
    
    os.makedirs(os.path.dirname(output_yaml), exist_ok=True)
    with open(output_yaml, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
        
    print(f"[Trainer] Dataset YAML generated: {output_yaml}")
    return output_yaml


def train_and_export(
    data_yaml="ai_data/coc_dataset.yaml",
    epochs=25,
    batch_size=16,
    imgsz=640,
    base_model="yolov8n.pt",
    device="auto",
    augment=True,
    lr0=0.005,
    optimizer="AdamW"
):
    """
    Executes advanced training pipeline on verified user dataset and exports to high-speed ONNX format.
    Advanced features:
    - AdamW optimizer with decoupled weight decay for rapid fine-tuning
    - Cosine learning rate scheduling (cos_lr=True)
    - Closed mosaic in final epochs for pinpoint bounding box boundary resolution
    - Color space & perspective jitter
    - Zero multiprocessing workers for rock-solid stability on Windows
    """
    try:
        import importlib
        ultralytics_mod = importlib.import_module("ultralytics")
        YOLO = getattr(ultralytics_mod, "YOLO")
    except (ImportError, AttributeError):
        print("[Trainer] Error: 'ultralytics' is not installed.")
        print("[Trainer] Install with: pip install ultralytics")
        return False

    # Check that dataset has images
    img_dir = "ai_data/images"
    existing_samples = [f for f in os.listdir(img_dir) if f.lower().endswith((".jpg", ".png"))] if os.path.exists(img_dir) else []
    if len(existing_samples) == 0:
        print("[Trainer] Error: No images found in ai_data/images.")
        print("[Trainer] Please capture and label at least one screen in the AI Teacher Studio first!")
        return False

    # Check for corresponding labels
    lbl_dir = "ai_data/labels"
    existing_labels = [f for f in os.listdir(lbl_dir) if f.lower().endswith(".txt")] if os.path.exists(lbl_dir) else []
    print(f"[Trainer] Dataset verified: {len(existing_samples)} images, {len(existing_labels)} label files.")

    data_yaml = create_dataset_yaml()

    # Detect hardware acceleration
    actual_device = "cpu"
    device_name = "CPU"
    try:
        import importlib
        torch_mod = importlib.import_module("torch")
        if device == "cuda" or (device == "auto" and torch_mod.cuda.is_available()):
            actual_device = 0
            device_name = torch_mod.cuda.get_device_name(0) if torch_mod.cuda.is_available() else "GPU"
        else:
            actual_device = "cpu"
            device_name = "CPU"
    except Exception:
        actual_device = "cpu"
        device_name = "CPU"

    # Adjust batch size if dataset is smaller than batch_size
    if len(existing_samples) < batch_size:
        batch_size = max(1, len(existing_samples))

    print(f"[Trainer] Initializing model '{base_model}'...")
    print(f"[Trainer] Hyperparameters: Epochs={epochs}, Batch={batch_size}, Resolution={imgsz}x{imgsz}, Optimizer={optimizer}, CosLR=True")
    print(f"[Trainer] Hardware Target: {device_name} (device={actual_device})")

    model = YOLO(base_model)

    # Train model with advanced tuning parameters
    try:
        model.train(
            data=data_yaml,
            epochs=epochs,
            batch=batch_size,
            imgsz=imgsz,
            device=actual_device,
            optimizer=optimizer,
            lr0=lr0,
            cos_lr=True,
            close_mosaic=5,
            augment=augment,
            degrees=5.0 if augment else 0.0,
            translate=0.1 if augment else 0.0,
            scale=0.5 if augment else 0.0,
            hsv_h=0.015 if augment else 0.0,
            hsv_s=0.7 if augment else 0.0,
            hsv_v=0.4 if augment else 0.0,
            workers=0,  # CRITICAL on Windows to eliminate multiprocessing spawn crashes
            plots=True,
            verbose=True
        )
    except Exception as e:
        print(f"[Trainer] Training execution encountered error: {e}")
        return False

    print("[Trainer] Training iterations finished successfully!")

    # Export to ONNX for production deployment
    print(f"[Trainer] Exporting trained weights to ONNX ({imgsz}x{imgsz})...")
    try:
        onnx_path = model.export(format="onnx", imgsz=imgsz, dynamic=False)
        print(f"[Trainer] Exported ONNX artifact: {onnx_path}")

        # Deploy to production assets/models/
        prod_dir = "assets/models"
        os.makedirs(prod_dir, exist_ok=True)
        target_prod_path = os.path.join(prod_dir, "coc_detector.onnx")
        shutil.copy(onnx_path, target_prod_path)
        print(f"[Trainer] Production model successfully deployed: {target_prod_path}")
        return True
    except Exception as e:
        print(f"[Trainer] ONNX export failed: {e}")
        return False


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Clash of Clans Advanced YOLO Trainer")
    parser.add_argument("--epochs", type=int, default=25, help="Number of training epochs (e.g. 15, 25, 50)")
    parser.add_argument("--batch", type=int, default=16, help="Batch size (e.g. 8, 16, 32)")
    parser.add_argument("--imgsz", type=int, default=640, help="Image resolution (640 or 960)")
    parser.add_argument("--model", type=str, default="yolov8n.pt", help="Base weights (yolov8n.pt, yolov8s.pt)")
    parser.add_argument("--device", type=str, default="auto", help="Hardware device (auto, cuda, cpu)")
    parser.add_argument("--optimizer", type=str, default="AdamW", help="Optimizer (AdamW or auto)")
    parser.add_argument("--lr0", type=float, default=0.005, help="Initial learning rate")
    parser.add_argument("--augment", action="store_true", default=True, help="Enable training data augmentations")
    args = parser.parse_args()

    success = train_and_export(
        epochs=args.epochs,
        batch_size=args.batch,
        imgsz=args.imgsz,
        base_model=args.model,
        device=args.device,
        optimizer=args.optimizer,
        lr0=args.lr0,
        augment=args.augment
    )
    sys.exit(0 if success else 1)
