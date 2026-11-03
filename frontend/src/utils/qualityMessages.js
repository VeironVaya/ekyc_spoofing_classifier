const QUALITY_REJECT_MESSAGES = {
  too_blurry: "That photo came out too blurry. Please retake it somewhere steady and well-lit.",
  too_dark: "That photo is too dark to use. Please retake it somewhere brighter.",
  too_bright: "That photo is overexposed. Please retake it out of direct glare.",
  resolution_too_low: "That photo's resolution is too low. Please retake it with a higher-quality camera.",
  no_face_detected: "We couldn't detect a face in that photo. Please make sure your face is clearly visible and try again.",
  face_too_small: "Your face is too small in the frame. Please move closer and retake the photo.",
};

export function qualityRejectMessage(reason) {
  return QUALITY_REJECT_MESSAGES[reason] || "That photo didn't pass the image quality check. Please retake it.";
}
