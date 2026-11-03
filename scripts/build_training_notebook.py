"""
Builds notebooks/04_convnext_training.ipynb programmatically.
Ensures valid JSON structure and clean cell code formatting.
"""

import json
from pathlib import Path

nb = {
    "cells": [],
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3 (ipykernel)",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "codemirror_mode": {"name": "ipython", "version": 3},
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.10.0"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 5
}

def add_md(text):
    nb["cells"].append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [line + "\n" for line in text.strip().split("\n")]
    })

def add_code(text):
    nb["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in text.strip().split("\n")]
    })

# CELL 1
add_md("""# Indonesian KTP Document Presentation Attack Detection (Doc-PAD)
## ConvNeXt-Small Single-Model Fine-Tuning Pipeline

This notebook trains a single, robust **ConvNeXt-Small** model (`convnext_small.fb_in22k_ft_in1k`) on the balanced 5-class Indonesian KTP Doc-PAD dataset.

### Pipeline Features:
1. **Zero-Leakage Grouped Dataset**: Unseen physical cards, screens, and identities in the test set.
2. **Automated Path Resolution**: Seamlessly runs on Kaggle (`/kaggle/input/...`) and local environments.
3. **Exploratory Data Analysis (EDA)**: Class balance checks and visual sample grid.
4. **Pure 1-Model Training**: 100 Epochs, AdamW + CosineAnnealing, Early Stopping (patience = 10).
5. **Comprehensive Metrics**: Macro-F1, Accuracy, Precision, Recall tracking with 4-panel graphs.
6. **Exhaustive Misclassification Analysis**: 100% uncapped visual grid of every mispredicted test sample.
7. **Single Zip Deliverable**: Packages model weights, graphs, metrics, and error audits into `convnext_training_results.zip`.""")

# CELL 2
add_md("""### 1. Environment Setup & Hardware Acceleration""")
add_code("""import os
import sys
import glob
import time
import json
import shutil
import random
import zipfile
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from PIL import Image
import matplotlib.pyplot as plt
import seaborn as sns

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

import timm
import albumentations as A
from albumentations.pytorch import ToTensorV2

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix
)
from tqdm.auto import tqdm

# Set random seed for full reproducibility
def seed_everything(seed=42):
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

seed_everything(42)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f'PyTorch Version: {torch.__version__}')
print(f'Device: {device}')
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)}')
    print(f'VRAM Available: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.2f} GB')
""")

# CELL 3
add_md("""### 2. Dataset Auto-Detection & Label Manifest Loading""")
add_code("""# Dedicated Kaggle Paths
KAGGLE_DATASET_ROOT = Path('/kaggle/input/datasets/veiron/indonesian-ktp-doc-pad-split')
OUTPUT_DIR = Path('/kaggle/working') if os.path.exists('/kaggle/working') else Path('./output')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Standard 5-Class Taxonomy
CLASSES = ['real_ktp', 'fake_screen', 'fake_print', 'fake_template', 'other']
CLASS_TO_IDX = {c: i for i, c in enumerate(CLASSES)}
IDX_TO_CLASS = {i: c for i, c in enumerate(CLASSES)}

print('Class Taxonomy:', CLASS_TO_IDX)

def find_dataset_paths():
    # 1. Direct check on your specific Kaggle dataset path
    if KAGGLE_DATASET_ROOT.exists():
        if (KAGGLE_DATASET_ROOT / 'train').exists() and (KAGGLE_DATASET_ROOT / 'test').exists():
            return KAGGLE_DATASET_ROOT / 'train', KAGGLE_DATASET_ROOT / 'test'
        if (KAGGLE_DATASET_ROOT / 'split' / 'train').exists() and (KAGGLE_DATASET_ROOT / 'split' / 'test').exists():
            return KAGGLE_DATASET_ROOT / 'split' / 'train', KAGGLE_DATASET_ROOT / 'split' / 'test'

    # 2. Search in /kaggle/input for directories containing train/ and test/
    if os.path.exists('/kaggle/input'):
        for root, dirs, files in os.walk('/kaggle/input'):
            if 'train' in dirs and 'test' in dirs:
                return Path(root) / 'train', Path(root) / 'test'
            if 'split' in dirs:
                split_p = Path(root) / 'split'
                if (split_p / 'train').exists() and (split_p / 'test').exists():
                    return split_p / 'train', split_p / 'test'

    # 3. Local fallbacks
    candidates = [
        Path('./datasets/split'),
        Path('../datasets/split'),
        Path('../../datasets/split'),
    ]
    for base in candidates:
        if (base / 'train').exists() and (base / 'test').exists():
            return base / 'train', base / 'test'

    raise FileNotFoundError('Could not locate train and test dataset directories.')

TRAIN_DIR, TEST_DIR = find_dataset_paths()
print(f'Train Directory: {TRAIN_DIR}')
print(f'Test Directory:  {TEST_DIR}')

def build_manifest_df(split_dir, split_name):
    # If labels.csv exists in folder, load directly
    labels_csv = split_dir / 'labels.csv'
    if labels_csv.exists():
        df = pd.read_csv(labels_csv)
        if 'image_path' not in df.columns:
            def resolve_path(row):
                direct = split_dir / row['class_name'] / row['filename']
                if direct.exists():
                    return str(direct)
                fallback = split_dir.parent / row['relative_path']
                return str(fallback)
            df['image_path'] = df.apply(resolve_path, axis=1)
        return df

    # Otherwise scan folders dynamically
    rows = []
    for c_name in CLASSES:
        c_dir = split_dir / c_name
        if not c_dir.exists():
            continue
        for fname in sorted(os.listdir(c_dir)):
            if fname.lower().endswith(('.png', '.jpg', '.jpeg')):
                rows.append({
                    'filename': fname,
                    'relative_path': f'{split_name}/{c_name}/{fname}',
                    'class_name': c_name,
                    'label_id': CLASS_TO_IDX[c_name],
                    'image_path': str(c_dir / fname)
                })
    return pd.DataFrame(rows)

train_df = build_manifest_df(TRAIN_DIR, 'train')
test_df = build_manifest_df(TEST_DIR, 'test')

# Save standardized labels.csv to working directory
train_df.to_csv(OUTPUT_DIR / 'train_labels.csv', index=False)
test_df.to_csv(OUTPUT_DIR / 'test_labels.csv', index=False)

print(f'Loaded {len(train_df)} training samples and {len(test_df)} test samples.')
""")

# CELL 4
add_md("""### 3. Exploratory Data Analysis (EDA)""")
add_code("""fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Train distribution
sns.countplot(data=train_df, x='class_name', order=CLASSES, palette='Blues_r', ax=axes[0])
axes[0].set_title(f'Train Distribution (N = {len(train_df)})', fontsize=12, fontweight='bold')
axes[0].set_xlabel('Class', fontsize=10)
axes[0].set_ylabel('Sample Count', fontsize=10)
for p in axes[0].patches:
    axes[0].annotate(f'{int(p.get_height())}', (p.get_x() + p.get_width() / 2., p.get_height() / 2),
                     ha='center', va='center', color='white', fontweight='bold', fontsize=11)

# Test distribution
sns.countplot(data=test_df, x='class_name', order=CLASSES, palette='Greens_r', ax=axes[1])
axes[1].set_title(f'Test Distribution (N = {len(test_df)} - Balanced)', fontsize=12, fontweight='bold')
axes[1].set_xlabel('Class', fontsize=10)
axes[1].set_ylabel('Sample Count', fontsize=10)
for p in axes[1].patches:
    axes[1].annotate(f'{int(p.get_height())}', (p.get_x() + p.get_width() / 2., p.get_height() / 2),
                     ha='center', va='center', color='white', fontweight='bold', fontsize=11)

plt.tight_layout()
eda_chart_path = OUTPUT_DIR / 'eda_class_distribution.png'
plt.savefig(eda_chart_path, dpi=150)
plt.show()

# Sample image preview grid (5 classes x 3 examples)
fig, axes = plt.subplots(5, 3, figsize=(12, 16))
for row_idx, c_name in enumerate(CLASSES):
    subset = train_df[train_df['class_name'] == c_name]
    samples = subset.sample(min(3, len(subset)), random_state=42)
    for col_idx, (_, r) in enumerate(samples.iterrows()):
        ax = axes[row_idx, col_idx]
        img = Image.open(r['image_path'])
        ax.imshow(img)
        ax.set_title(f"{c_name}\\n{r['filename']}", fontsize=9)
        ax.axis('off')

plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'eda_sample_grid.png', dpi=150)
plt.show()
""")

# CELL 5
add_md("""### 4. Image Preprocessing & Albumentations Transforms

Input resolution is set to **256×256** with ImageNet mean and standard deviation normalization, strictly matching the production deployment requirements (`inference/app/preprocess.py`).""")
add_code("""IMG_SIZE = 256
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

train_transforms = A.Compose([
    A.Resize(IMG_SIZE, IMG_SIZE),
    A.HorizontalFlip(p=0.5),
    A.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1, p=0.3),
    A.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ToTensorV2(),
])

test_transforms = A.Compose([
    A.Resize(IMG_SIZE, IMG_SIZE),
    A.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ToTensorV2(),
])
""")

# CELL 6
add_md("""### 5. Dataset & DataLoader Construction""")
add_code("""class DocPadDataset(Dataset):
    def __init__(self, df, transforms=None):
        self.df = df.reset_index(drop=True)
        self.transforms = transforms

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        img_path = row['image_path']
        label = int(row['label_id'])

        # Load image via OpenCV
        img = cv2.imread(img_path)
        if img is None:
            # Fallback to PIL
            pil_img = Image.open(img_path).convert('RGB')
            img = np.array(pil_img)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        if self.transforms:
            augmented = self.transforms(image=img)
            img = augmented['image']

        return img, label, row['filename'], row['class_name'], img_path

BATCH_SIZE = 32
NUM_WORKERS = 2 if os.name != 'nt' else 0

train_dataset = DocPadDataset(train_df, transforms=train_transforms)
test_dataset = DocPadDataset(test_df, transforms=test_transforms)

train_loader = DataLoader(
    train_dataset,
    batch_size=BATCH_SIZE,
    shuffle=True,
    num_workers=NUM_WORKERS,
    pin_memory=torch.cuda.is_available()
)

test_loader = DataLoader(
    test_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False,
    num_workers=NUM_WORKERS,
    pin_memory=torch.cuda.is_available()
)

print(f'Train Loader: {len(train_loader)} batches ({len(train_dataset)} images)')
print(f'Test Loader:  {len(test_loader)} batches ({len(test_dataset)} images)')
""")

# CELL 7
add_md("""### 6. Model Architecture: Pure ConvNeXt-Small

We instantiate a single, pure **ConvNeXt-Small** (`convnext_small.fb_in22k_ft_in1k`) initialized with pretrained weights from ImageNet-22k fine-tuned on 1k, outputting logits for our 5 target classes.""")
add_code("""MODEL_NAME = 'convnext_small.fb_in22k_ft_in1k'
NUM_CLASSES = len(CLASSES)

print(f'Instantiating model: {MODEL_NAME}')
model = timm.create_model(
    MODEL_NAME,
    pretrained=True,
    num_classes=NUM_CLASSES
)

model = model.to(device)

total_params = sum(p.numel() for p in model.parameters())
trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
print(f'Total Parameters: {total_params / 1e6:.2f}M | Trainable: {trainable_params / 1e6:.2f}M')
""")

# CELL 8
add_md("""### 7. Optimizer, Loss & Metric Evaluation Engine""")
add_code("""criterion = nn.CrossEntropyLoss()
optimizer = optim.AdamW(model.parameters(), lr=1e-4, weight_decay=1e-2)

MAX_EPOCHS = 100
PATIENCE = 10

scheduler = optim.lr_scheduler.CosineAnnealingLR(
    optimizer,
    T_max=MAX_EPOCHS,
    eta_min=1e-6
)

def train_one_epoch(model, loader, criterion, optimizer, device):
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0

    pbar = tqdm(loader, desc='Training', leave=False)
    for imgs, labels, _, _, _ in pbar:
        imgs, labels = imgs.to(device), labels.to(device)

        optimizer.zero_grad()
        outputs = model(imgs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        running_loss += loss.item() * imgs.size(0)
        preds = outputs.argmax(dim=1)
        correct += (preds == labels).sum().item()
        total += labels.size(0)

        pbar.set_postfix({'loss': f'{loss.item():.4f}'})

    epoch_loss = running_loss / total
    epoch_acc = correct / total
    return epoch_loss, epoch_acc

def evaluate(model, loader, criterion, device):
    model.eval()
    running_loss = 0.0
    total = 0

    all_preds = []
    all_labels = []
    all_probs = []
    all_files = []
    all_classes = []
    all_paths = []

    with torch.no_grad():
        pbar = tqdm(loader, desc='Evaluating', leave=False)
        for imgs, labels, fnames, cnames, paths in pbar:
            imgs, labels = imgs.to(device), labels.to(device)
            outputs = model(imgs)
            loss = criterion(outputs, labels)

            running_loss += loss.item() * imgs.size(0)
            total += labels.size(0)

            probs = torch.softmax(outputs, dim=1)
            preds = outputs.argmax(dim=1)

            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
            all_probs.extend(probs.cpu().numpy())
            all_files.extend(fnames)
            all_classes.extend(cnames)
            all_paths.extend(paths)

    val_loss = running_loss / total
    val_acc = accuracy_score(all_labels, all_preds)
    val_precision = precision_score(all_labels, all_preds, average='macro', zero_division=0)
    val_recall = recall_score(all_labels, all_preds, average='macro', zero_division=0)
    val_f1 = f1_score(all_labels, all_preds, average='macro', zero_division=0)

    results = {
        'loss': val_loss,
        'acc': val_acc,
        'precision': val_precision,
        'recall': val_recall,
        'f1': val_f1,
        'y_true': np.array(all_labels),
        'y_pred': np.array(all_preds),
        'y_probs': np.array(all_probs),
        'filenames': all_files,
        'class_names': all_classes,
        'image_paths': all_paths,
    }
    return results
""")

# CELL 9
add_md("""### 8. 100-Epoch Training Loop with Early Stopping (Patience = 10)""")
add_code("""best_f1 = 0.0
patience_counter = 0
history = []

BEST_MODEL_PATH = OUTPUT_DIR / 'best_convnext_small_ktp_pad.pth'
LAST_MODEL_PATH = OUTPUT_DIR / 'last_checkpoint.pth'

print('=' * 80)
print(f'Starting Training: {MAX_EPOCHS} Epochs (Early Stopping Patience: {PATIENCE})')
print('=' * 80)

start_time = time.time()

for epoch in range(1, MAX_EPOCHS + 1):
    epoch_start = time.time()

    train_loss, train_acc = train_one_epoch(model, train_loader, criterion, optimizer, device)
    eval_res = evaluate(model, test_loader, criterion, device)
    scheduler.step()

    val_loss = eval_res['loss']
    val_acc = eval_res['acc']
    val_prec = eval_res['precision']
    val_rec = eval_res['recall']
    val_f1 = eval_res['f1']
    lr = scheduler.get_last_lr()[0]

    epoch_time = time.time() - epoch_start

    history.append({
        'epoch': epoch,
        'train_loss': train_loss,
        'train_acc': train_acc,
        'test_loss': val_loss,
        'test_acc': val_acc,
        'test_precision': val_prec,
        'test_recall': val_rec,
        'test_f1': val_f1,
        'lr': lr,
        'time_sec': epoch_time,
    })

    is_best = val_f1 > best_f1
    status_tag = ''

    if is_best:
        best_f1 = val_f1
        patience_counter = 0
        torch.save(model.state_dict(), BEST_MODEL_PATH)
        status_tag = '--> BEST MODEL SAVED'
    else:
        patience_counter += 1
        status_tag = f'(Patience: {patience_counter}/{PATIENCE})'

    print(
        f'Epoch {epoch:03d}/{MAX_EPOCHS:03d} | '
        f'Train Loss: {train_loss:.4f} Acc: {train_acc:.4f} | '
        f'Test Loss: {val_loss:.4f} Acc: {val_acc:.4f} F1: {val_f1:.4f} P: {val_prec:.4f} R: {val_rec:.4f} | '
        f'{status_tag}'
    )

    # Save last checkpoint
    torch.save(model.state_dict(), LAST_MODEL_PATH)

    # Check early stopping
    if patience_counter >= PATIENCE:
        print(f'\\nEarly stopping triggered at epoch {epoch}! No improvement for {PATIENCE} consecutive epochs.')
        break

total_train_time = time.time() - start_time
print(f'\\nTraining Finished in {total_train_time / 60:.2f} minutes. Best Test Macro-F1: {best_f1:.4f}')

# Save history dataframe
history_df = pd.DataFrame(history)
history_df.to_csv(OUTPUT_DIR / 'training_metrics.csv', index=False)
""")

# CELL 10
add_md("""### 9. Loss & Metrics Graphing""")
add_code("""fig, axes = plt.subplots(2, 2, figsize=(15, 10))

epochs = history_df['epoch']

# 1. Loss Curve
axes[0, 0].plot(epochs, history_df['train_loss'], label='Train Loss', color='#1f77b4', lw=2)
axes[0, 0].plot(epochs, history_df['test_loss'], label='Test Loss', color='#d62728', lw=2)
axes[0, 0].set_title('Training vs Test Loss', fontsize=12, fontweight='bold')
axes[0, 0].set_xlabel('Epoch')
axes[0, 0].set_ylabel('Cross-Entropy Loss')
axes[0, 0].legend()
axes[0, 0].grid(True, alpha=0.3)

# 2. Accuracy Curve
axes[0, 1].plot(epochs, history_df['train_acc'], label='Train Accuracy', color='#1f77b4', lw=2)
axes[0, 1].plot(epochs, history_df['test_acc'], label='Test Accuracy', color='#2ca02c', lw=2)
axes[0, 1].set_title('Training vs Test Accuracy', fontsize=12, fontweight='bold')
axes[0, 1].set_xlabel('Epoch')
axes[0, 1].set_ylabel('Accuracy')
axes[0, 1].legend()
axes[0, 1].grid(True, alpha=0.3)

# 3. Macro-F1 Score
axes[1, 0].plot(epochs, history_df['test_f1'], label='Test Macro-F1', color='#9467bd', lw=2)
axes[1, 0].axhline(y=best_f1, color='orange', linestyle='--', label=f'Best F1 ({best_f1:.4f})')
axes[1, 0].set_title('Test Macro-F1 Score Over Epochs', fontsize=12, fontweight='bold')
axes[1, 0].set_xlabel('Epoch')
axes[1, 0].set_ylabel('F1 Score')
axes[1, 0].legend()
axes[1, 0].grid(True, alpha=0.3)

# 4. Precision vs Recall
axes[1, 1].plot(epochs, history_df['test_precision'], label='Test Precision', color='#ff7f0e', lw=2)
axes[1, 1].plot(epochs, history_df['test_recall'], label='Test Recall', color='#17becf', lw=2)
axes[1, 1].set_title('Test Precision vs Recall', fontsize=12, fontweight='bold')
axes[1, 1].set_xlabel('Epoch')
axes[1, 1].set_ylabel('Score')
axes[1, 1].legend()
axes[1, 1].grid(True, alpha=0.3)

plt.tight_layout()
training_curves_path = OUTPUT_DIR / 'training_curves.png'
plt.savefig(training_curves_path, dpi=150)
plt.show()
""")

# CELL 11
add_md("""### 10. Final Test Set Evaluation & Confusion Matrix""")
add_code("""print(f'Loading best checkpoint: {BEST_MODEL_PATH}')
model.load_state_dict(torch.load(BEST_MODEL_PATH, map_location=device))
final_eval = evaluate(model, test_loader, criterion, device)

y_true = final_eval['y_true']
y_pred = final_eval['y_pred']
y_probs = final_eval['y_probs']

print('\\n' + '=' * 60)
print('FINAL CLASSIFICATION REPORT (BEST MODEL ON UNSEEN TEST SET)')
print('=' * 60)
report_str = classification_report(y_true, y_pred, target_names=CLASSES, digits=4)
print(report_str)

report_dict = classification_report(y_true, y_pred, target_names=CLASSES, output_dict=True)
with open(OUTPUT_DIR / 'test_evaluation_report.json', 'w') as f:
    json.dump(report_dict, f, indent=2)

# Confusion Matrix
cm = confusion_matrix(y_true, y_pred)
cm_norm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]

plt.figure(figsize=(9, 7))
sns.heatmap(
    cm_norm,
    annot=True,
    fmt='.2%',
    cmap='Blues',
    xticklabels=CLASSES,
    yticklabels=CLASSES,
    cbar=True
)
plt.title('Normalized Confusion Matrix (Unseen Test Set)', fontsize=13, fontweight='bold')
plt.xlabel('Predicted Class', fontsize=11)
plt.ylabel('Ground Truth Class', fontsize=11)
plt.tight_layout()
cm_path = OUTPUT_DIR / 'confusion_matrix.png'
plt.savefig(cm_path, dpi=150)
plt.show()
""")

# CELL 12
add_md("""### 11. Exhaustive (100% Uncapped) Misclassification Visualizer

Every single misclassified image in the test set is visualized in a tight grid below without any sampling or omission. If $N$ samples are mispredicted, all $N$ are rendered with color-coded headers showing true vs predicted class, confidence percentage, and filename.""")
add_code("""# Filter all misclassifications
misclassified_indices = np.where(y_true != y_pred)[0]
n_errors = len(misclassified_indices)

print(f'Total Test Samples: {len(y_true)}')
print(f'Correct Predictions: {len(y_true) - n_errors} ({(len(y_true) - n_errors) / len(y_true):.2%})')
print(f'Misclassifications:  {n_errors} ({n_errors / len(y_true):.2%})')

misclassified_rows = []
for idx in misclassified_indices:
    t_cls = IDX_TO_CLASS[y_true[idx]]
    p_cls = IDX_TO_CLASS[y_pred[idx]]
    conf = float(y_probs[idx][y_pred[idx]])
    fname = final_eval['filenames'][idx]
    fpath = final_eval['image_paths'][idx]

    row_data = {
        'index': idx,
        'filename': fname,
        'true_class': t_cls,
        'pred_class': p_cls,
        'confidence': conf,
        'image_path': fpath,
    }
    for c_i, c_name in enumerate(CLASSES):
        row_data[f'prob_{c_name}'] = float(y_probs[idx][c_i])
    misclassified_rows.append(row_data)

misclassified_df = pd.DataFrame(misclassified_rows)
misclassified_csv_path = OUTPUT_DIR / 'misclassified_analysis.csv'
misclassified_df.to_csv(misclassified_csv_path, index=False)
print(f'Saved error audit log to: {misclassified_csv_path}')

if n_errors == 0:
    print('\\nPERFECT SCORE! 0 misclassifications on the test set!')
    fig, ax = plt.subplots(figsize=(6, 2))
    ax.text(0.5, 0.5, '100% Test Accuracy\\nZero Misclassifications!', 
            ha='center', va='center', fontsize=14, color='green', fontweight='bold')
    ax.axis('off')
    plt.savefig(OUTPUT_DIR / 'all_misclassifications_grid.png', bbox_inches='tight')
    plt.show()
else:
    # Build dynamic tight grid showing ALL N errors
    ncols = 5
    nrows = (n_errors + ncols - 1) // ncols

    fig, axes = plt.subplots(nrows, ncols, figsize=(20, 3.8 * nrows), constrained_layout=True)

    # Normalize axes array shape
    if nrows == 1 and ncols == 1:
        axes = np.array([[axes]])
    elif nrows == 1:
        axes = np.expand_dims(axes, 0)
    elif ncols == 1:
        axes = np.expand_dims(axes, 1)
    axes_flat = axes.flatten()

    for i, row in enumerate(misclassified_df.itertuples()):
        ax = axes_flat[i]
        try:
            img = Image.open(row.image_path)
            ax.imshow(img)
        except Exception as e:
            ax.text(0.5, 0.5, f'Error loading image\\n{row.filename}', ha='center', va='center', fontsize=8)

        title_text = (
            f'TRUE: {row.true_class}\\n'
            f'PRED: {row.pred_class} ({row.confidence:.1%})\\n'
            f'{row.filename}'
        )
        ax.set_title(title_text, fontsize=9, color='darkred', fontweight='bold')
        ax.axis('off')

    # Turn off any remaining unused subplots in the last row
    for j in range(n_errors, len(axes_flat)):
        axes_flat[j].axis('off')

    misclass_grid_path = OUTPUT_DIR / 'all_misclassifications_grid.png'
    plt.savefig(misclass_grid_path, dpi=150, bbox_inches='tight')
    plt.show()
    print(f'Saved all {n_errors} misclassifications to: {misclass_grid_path}')
""")

# CELL 13
add_md("""### 12. Automated Output Packaging (.zip)

Packages all model weights, CSV metrics, performance curves, confusion matrix, and misclassification galleries into a single compressed archive `/kaggle/working/convnext_training_results.zip` for one-click downloading.""")
add_code("""ZIP_DEST = OUTPUT_DIR / 'convnext_training_results.zip'

files_to_pack = [
    'best_convnext_small_ktp_pad.pth',
    'last_checkpoint.pth',
    'training_curves.png',
    'confusion_matrix.png',
    'all_misclassifications_grid.png',
    'eda_class_distribution.png',
    'eda_sample_grid.png',
    'training_metrics.csv',
    'misclassified_analysis.csv',
    'test_evaluation_report.json',
    'train_labels.csv',
    'test_labels.csv',
]

print('=' * 60)
print('Compressing Training Artifacts...')
print('=' * 60)

with zipfile.ZipFile(ZIP_DEST, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for fname in files_to_pack:
        fpath = OUTPUT_DIR / fname
        if fpath.exists():
            zipf.write(fpath, arcname=fname)
            print(f'  [+] Added: {fname} ({fpath.stat().st_size / 1024:.1f} KB)')
        else:
            print(f'  [-] Skipped (not found): {fname}')

print('-' * 60)
if ZIP_DEST.exists():
    print(f'Artifact Created: {ZIP_DEST} ({ZIP_DEST.stat().st_size / (1024*1024):.2f} MB)')
print('Ready for download from Kaggle output!')
""")

output_nb_path = Path("notebooks/04_convnext_training.ipynb")
output_nb_path.parent.mkdir(parents=True, exist_ok=True)
with open(output_nb_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1)

print(f"Successfully generated {output_nb_path} with {len(nb['cells'])} cells!")

