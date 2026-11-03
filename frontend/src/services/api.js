const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8080";

const DEFAULT_TIMEOUT_MS = 15000;
// eKYC checks chain liveness + OCR + face-match server-side (backend's own
// call to the inference service times out at 30s) - give it more room here
// so the frontend doesn't abort a request the backend was about to finish.
const EKYC_TIMEOUT_MS = 45000;

async function request(url, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  let response;
  try {
    response = await fetch(url, { ...options, signal: controller.signal });
  } catch (err) {
    if (err.name === "AbortError") {
      throw new Error("The request timed out. The server may be busy - try again in a moment.");
    }
    throw new Error("Could not reach the server. Check your connection and that the backend is running.");
  } finally {
    clearTimeout(timeoutId);
  }

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error("Invalid admin API key.");
    }
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || `Request failed with status ${response.status}`);
  }

  return response;
}

export async function verifySelfie(idNumber, selfieBlob) {
  const formData = new FormData();
  formData.append("id_number", idNumber);
  formData.append("selfie", selfieBlob, "selfie.jpg");

  const response = await request(
    `${API_URL}/verify`,
    { method: "POST", body: formData },
    EKYC_TIMEOUT_MS
  );
  return response.json();
}

export async function fetchAttempts(apiKey) {
  const response = await request(`${API_URL}/admin/attempts`, {
    headers: { Authorization: `Bearer ${apiKey}` },
  });
  return response.json();
}

export async function fetchAttemptImageUrl(id, apiKey) {
  const response = await request(`${API_URL}/admin/attempts/${id}/image`, {
    headers: { Authorization: `Bearer ${apiKey}` },
  });
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

export async function previewEkyc(idCardBlob, selfieBlob) {
  const formData = new FormData();
  formData.append("id_card", idCardBlob, "id_card.jpg");
  formData.append("selfie", selfieBlob, "selfie.jpg");

  const response = await request(
    `${API_URL}/register/preview`,
    { method: "POST", body: formData },
    EKYC_TIMEOUT_MS
  );
  return response.json();
}

export async function registerEkyc(idCardBlob, selfieBlob, fields) {
  const formData = new FormData();
  formData.append("id_card", idCardBlob, "id_card.jpg");
  formData.append("selfie", selfieBlob, "selfie.jpg");
  if (fields?.nik) formData.append("nik", fields.nik);
  if (fields?.name) formData.append("name", fields.name);
  if (fields?.dob) formData.append("dob", fields.dob);

  const response = await request(
    `${API_URL}/register`,
    { method: "POST", body: formData },
    EKYC_TIMEOUT_MS
  );
  return response.json();
}

export async function fetchRegistrations(apiKey) {
  const response = await request(`${API_URL}/admin/registrations`, {
    headers: { Authorization: `Bearer ${apiKey}` },
  });
  return response.json();
}

export async function updateRegistrationDecision(id, decision, apiKey) {
  const response = await request(`${API_URL}/admin/registrations/${id}/decision`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ decision }),
  });
  return response.json();
}

export async function fetchApiRequests(apiKey) {
  const response = await request(`${API_URL}/admin/api-requests`, {
    headers: { Authorization: `Bearer ${apiKey}` },
  });
  return response.json();
}

export async function fetchRegistrationImageUrl(id, type, apiKey) {
  const response = await request(`${API_URL}/admin/registrations/${id}/image?type=${type}`, {
    headers: { Authorization: `Bearer ${apiKey}` },
  });
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

// Mode 4: Standalone KTP Forgery (Doc-PAD) Check
export async function checkKtpForgery(idCardBlob, mockClass = "") {
  const formData = new FormData();
  formData.append("file", idCardBlob, "ktp_card.jpg");
  if (mockClass) {
    formData.append("mock_class", mockClass);
  }

  const response = await request(
    `${API_URL}/ktp-forgery`,
    { method: "POST", body: formData },
    EKYC_TIMEOUT_MS
  );
  return response.json();
}

// Mode 3: Complete Pipeline Preview (KTP Doc-PAD + OCR + Face Match + Selfie Liveness)
export async function previewCompletePipeline(idCardBlob, selfieBlob, mockKtpClass = "") {
  const formData = new FormData();
  formData.append("id_card", idCardBlob, "id_card.jpg");
  formData.append("selfie", selfieBlob, "selfie.jpg");
  if (mockKtpClass) {
    formData.append("mock_ktp_class", mockKtpClass);
  }

  const response = await request(
    `${API_URL}/pipeline/preview`,
    { method: "POST", body: formData },
    EKYC_TIMEOUT_MS
  );
  return response.json();
}

// Mode 3: Complete Pipeline Final Registration
export async function registerCompletePipeline(idCardBlob, selfieBlob, fields) {
  const formData = new FormData();
  formData.append("id_card", idCardBlob, "id_card.jpg");
  formData.append("selfie", selfieBlob, "selfie.jpg");
  if (fields?.nik) formData.append("nik", fields.nik);
  if (fields?.name) formData.append("name", fields.name);
  if (fields?.dob) formData.append("dob", fields.dob);

  const response = await request(
    `${API_URL}/pipeline/register`,
    { method: "POST", body: formData },
    EKYC_TIMEOUT_MS
  );
  return response.json();
}
