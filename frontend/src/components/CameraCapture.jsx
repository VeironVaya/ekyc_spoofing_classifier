import { useCallback, useEffect, useRef, useState } from "react";

function describeCameraError(err) {
  switch (err.name) {
    case "NotAllowedError":
    case "SecurityError":
      return "Camera access was denied. Allow camera permission in your browser's site settings and try again.";
    case "NotFoundError":
    case "OverconstrainedError":
      return "No camera was found on this device.";
    case "NotReadableError":
      return "The camera is already in use by another app or tab.";
    default:
      return "Could not access the camera: " + (err.message || err.name || "unknown error");
  }
}

export default function CameraCapture({ onCapture }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [error, setError] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setIsStreaming(false);
  }, []);

  // Make sure the camera is always released if the user navigates away or
  // this component unmounts mid-stream - otherwise the camera light stays on.
  useEffect(() => stopCamera, [stopCamera]);

  const startCamera = useCallback(async () => {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("This browser doesn't support camera access. Try a recent Chrome, Edge, or Firefox.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user" },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setIsStreaming(true);
    } catch (err) {
      setError(describeCameraError(err));
    }
  }, []);

  const capture = useCallback(() => {
    const video = videoRef.current;
    if (!video || !video.videoWidth) {
      setError("Camera isn't ready yet - wait a moment and try again.");
      return;
    }

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);

    canvas.toBlob(
      (blob) => {
        if (blob) {
          onCapture(blob);
        } else {
          setError("Could not capture the photo. Try again.");
        }
      },
      "image/jpeg",
      0.92
    );

    stopCamera();
  }, [onCapture, stopCamera]);

  return (
    <div className="camera-capture">
      <video ref={videoRef} autoPlay playsInline muted className="camera-preview" />
      {error && <p className="camera-error">{error}</p>}
      <div className="camera-controls">
        {!isStreaming ? (
          <button type="button" onClick={startCamera}>
            Start Camera
          </button>
        ) : (
          <button type="button" onClick={capture}>
            Capture Selfie
          </button>
        )}
      </div>
    </div>
  );
}
