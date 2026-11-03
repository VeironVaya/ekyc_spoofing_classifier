# Kaggle Training & Deployment Guide: ConvNeXt-Small Doc-PAD

This guide provides a step-by-step walkthrough to train the **Indonesian KTP Document Presentation Attack Detection (Doc-PAD)** model on Kaggle using a GPU, run it headlessly via terminal to avoid browser disconnect timeouts, and deploy the resulting model back into your FastAPI inference service.

---

## Prerequisites & Checklist

Before starting, verify you have:
- [x] Partitioned dataset ready in `datasets/split/` (`train/` with 2,088 images, `test/` with 540 images).
- [x] Generated label manifests: `datasets/split/train/labels.csv` and `datasets/split/test/labels.csv`.
- [x] All-in-one standalone training notebook: [`notebooks/04_convnext_training.ipynb`](file:///c:/Users/veiro/Documents/research/ekyc/notebooks/04_convnext_training.ipynb).
- [x] A Kaggle account ([kaggle.com](https://www.kaggle.com/)).

---

## Step 1: Upload the Dataset to Kaggle

### Your Kaggle Setup:
- **Kaggle Username**: `veiron`
- **Dataset Input Path**: `/kaggle/input/datasets/veiron/indonesian-ktp-doc-pad-split`
- **Output Working Directory**: `/kaggle/working/`
- **Dataset Title**: `Indonesian KTP Doc-PAD Split`
- **Dataset Slug**: `veiron/indonesian-ktp-doc-pad-split`

### Option A: Upload via Kaggle Web Interface (Simplest)
1. Open your browser and navigate to [kaggle.com/datasets](https://www.kaggle.com/datasets).
2. Click the **"+ New Dataset"** button in the top right.
3. In the modal:
   - Enter Dataset Title: `Indonesian KTP Doc-PAD Split`
   - Drag and drop your zipped dataset folder (the zip containing `train/` and `test/` folders, or the `split/` folder).
4. Click **"Create"**.
5. Wait 1–2 minutes for Kaggle to process and unpack the zip.

### Option B: Upload via Terminal (Kaggle CLI)
If you have the Kaggle CLI installed (`pip install kaggle`):
```bash
# 1. Create a metadata file
cat <<EOF > datasets/dataset-metadata.json
{
  "title": "Indonesian KTP Doc-PAD Split",
  "id": "veiron/indonesian-ktp-doc-pad-split",
  "licenses": [{"name": "CC0-1.0"}]
}
EOF

# 2. Push the dataset
kaggle datasets create -p datasets/split -u
```

---

## Step 2: Create & Configure the Kaggle Notebook

1. Go to [kaggle.com/code](https://www.kaggle.com/code) and click **"+ New Notebook"**.
2. From the top navigation menu, click **File $\rightarrow$ Upload Notebook**.
3. Select your local file: [`notebooks/04_convnext_training.ipynb`](file:///c:/Users/veiro/Documents/research/ekyc/notebooks/04_convnext_training.ipynb).
4. In the right-hand panel (**Notebook options**), configure:
   - **Accelerator**: Select **GPU T4 x2** or **GPU P100** *(Mandatory for fast training)*.
   - **Internet**: Toggle to **ON** *(Mandatory for `timm` to download pretrained ConvNeXt weights)*.
5. In the right-hand panel, under **Input**, click **"+ Add Input"** (or **Add Data**):
   - Search for your dataset: `indonesian-ktp-doc-pad-split` (or under "Your Datasets").
   - Click the **"+"** icon next to it to attach it to the notebook.

---

## Step 3: Run Training (Avoid Disconnect Timeouts)

### Why NOT just run in browser interactive mode?
Interactive sessions in Kaggle have an idle timeout (closing the browser tab, putting your laptop to sleep, or temporary network drops can kill your session).

### The Solution: Run via Headless Commit / Terminal (12-Hour Execution Limit)

#### Method A: Terminal Execution via Kaggle CLI
You can launch the training job directly from your local terminal and close your PC:

1. Ensure your Kaggle API key (`kaggle.json`) is placed in `~/.kaggle/kaggle.json` (on Windows: `C:\Users\<user>\.kaggle\kaggle.json`).
2. Create a folder `kaggle_runner/` and add `kernel-metadata.json`:
   ```json
   {
     "id": "veiron/ktp-convnext-training",
     "title": "KTP ConvNeXt Training",
     "code_file": "notebooks/04_convnext_training.ipynb",
     "language": "python",
     "kernel_type": "notebook",
     "is_private": "true",
     "enable_gpu": "true",
     "enable_internet": "true",
     "dataset_sources": [
       "veiron/indonesian-ktp-doc-pad-split"
     ]
   }
   ```
3. Push and execute headlessly:
   ```bash
   kaggle kernels push -p .
   ```
4. Monitor progress anytime:
   ```bash
   kaggle kernels status veiron/ktp-convnext-training
   ```
   Status will transition: `queued` $\rightarrow$ `running` $\rightarrow$ `complete`.

#### Method B: Web UI "Save & Run All (Commit)"
1. Inside the Kaggle notebook editor, look at the top right header.
2. Click **"Save Version"**.
3. In the dialog, select **"Save & Run All (Commit)"** (Advanced Settings: GPU enabled, Internet enabled).
4. Click **"Save"**.
5. You can now close your browser tab completely! The notebook will execute in Kaggle's cloud background container for up to 12 hours.

---

## Step 4: Training Process & Expected Timeline

| Stage | What Happens | Approx. Duration |
|---|---|---|
| **EDA & Loading** | Scans 2,088 train & 540 test images, plots distributions. | ~15 seconds |
| **Model Init** | Downloads `convnext_small.fb_in22k_ft_in1k` weights via `timm`. | ~30 seconds |
| **Training Loop** | 100 epochs max, batch size 32 on GPU T4. | ~15–20 sec/epoch |
| **Early Stopping** | Monitored on test Macro-F1 (triggers if no gain for 10 epochs). | Expected ~25–40 epochs (~10–15 min) |
| **Evaluation** | Evaluates best checkpoint on test set, builds confusion matrix. | ~20 seconds |
| **Error Visualizer**| Renders tight grid of **all** misclassified test samples. | ~15 seconds |
| **Zipping** | Compresses all artifacts into `convnext_training_results.zip`. | ~10 seconds |

---

## Step 5: Download the Output Zip

Once training completes (status: `complete`):

### Option A: Web Interface Download
1. Open your notebook's viewer page on Kaggle (e.g. `kaggle.com/veiron/ktp-convnext-training`).
2. Navigate to the **"Output"** tab on the right side.
3. Locate `/kaggle/working/convnext_training_results.zip`.
4. Click the three dots icon next to it and select **"Download"** (or click the Download button).

### Option B: Terminal CLI Download
```bash
kaggle kernels output veiron/ktp-convnext-training -p ./kaggle_output
```

---

## Step 6: Inspect Results & Error Analysis

Extract `convnext_training_results.zip`. The folder will contain:

```
convnext_training_results/
├── best_convnext_small_ktp_pad.pth      # The winning model weights (clean state_dict)
├── last_checkpoint.pth                  # The final epoch weights
├── training_curves.png                  # Loss & Accuracy & F1 curves across epochs
├── confusion_matrix.png                 # Normalized confusion matrix heatmap
├── all_misclassifications_grid.png      # VISUAL GRID of all cards the model got wrong
├── misclassified_analysis.csv           # Detailed spreadsheet of mispredicted samples & probabilities
├── eda_class_distribution.png           # Dataset distribution bar charts
├── eda_sample_grid.png                  # 5-class visual preview
├── training_metrics.csv                 # Epoch-by-epoch history
└── test_evaluation_report.json          # Precision, Recall, F1 per class
```

### Key Visual Checks:
1. **`all_misclassifications_grid.png`**: Inspect every failed image to understand edge cases (e.g., extreme glare, severe motion blur, or ambiguous synthetic templates).
2. **`confusion_matrix.png`**: Confirm high diagonal accuracy and check which classes have mutual false positives.

---

## Step 7: Deploy the Model to Your FastAPI Service

To integrate the newly trained model into your local or production e-KYC service:

1. **Copy Model Weights**:
   Copy `best_convnext_small_ktp_pad.pth` into your project repository:
   ```bash
   cp best_convnext_small_ktp_pad.pth inference/model/model_fold_0.pth
   ```

2. **Verify Architecture in [`inference/app/model_loader.py`](file:///c:/Users/veiro/Documents/research/ekyc/inference/app/model_loader.py)**:
   Ensure `ARCHITECTURE` and `NUM_CLASSES` are set:
   ```python
   ARCHITECTURE = "convnext_small.fb_in22k_ft_in1k"
   NUM_CLASSES = 5
   ```

3. **Verify Class Order in [`inference/app/main.py`](file:///c:/Users/veiro/Documents/research/ekyc/inference/app/main.py)**:
   ```python
   CLASSES = [
       "real_ktp",
       "fake_screen",
       "fake_print",
       "fake_template",
       "other"
   ]
   ```

4. **Start the Inference Container & Test**:
   ```bash
   docker compose up --build inference
   ```
   Verify health status:
   ```bash
   curl http://localhost:8000/health
   # Response: {"status":"ok","model_loaded":true}
   ```

