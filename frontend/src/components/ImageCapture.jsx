import { useState } from "react";
import CameraCapture from "./CameraCapture";

// Lets the user provide an image either by uploading a file or by taking a
// live photo with the camera, with a tab to switch between the two.
export default function ImageCapture({
  title,
  preview,
  onCapture,
  onClear,
  onError,
  disabled,
  defaultMode = "upload",
}) {
  const [mode, setMode] = useState(defaultMode);

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      onError?.("Please choose an image file.");
      return;
    }
    onCapture(file);
  };

  return (
    <div className="image-capture-field">
      <span className="field-label">{title}</span>

      {preview ? (
        <div className="selfie-preview">
          <img src={preview} alt={title} />
          <button type="button" className="secondary" onClick={onClear} disabled={disabled}>
            Change Photo
          </button>
        </div>
      ) : (
        <div className="image-capture">
          <div className="image-capture-tabs">
            <button
              type="button"
              className={mode === "upload" ? "active" : ""}
              onClick={() => setMode("upload")}
              disabled={disabled}
            >
              Upload File
            </button>
            <button
              type="button"
              className={mode === "camera" ? "active" : ""}
              onClick={() => setMode("camera")}
              disabled={disabled}
            >
              Use Camera
            </button>
          </div>

          {mode === "upload" ? (
            <input
              type="file"
              accept="image/*"
              onChange={handleFileChange}
              disabled={disabled}
              aria-label={title}
            />
          ) : (
            <CameraCapture onCapture={onCapture} />
          )}
        </div>
      )}
    </div>
  );
}
