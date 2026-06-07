/**
 * API service for communicating with the FastAPI backend.
 */

const API_BASE = '/api';

async function request(url, options = {}) {
  const response = await fetch(`${API_BASE}${url}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || `Request failed with status ${response.status}`;
    throw new Error(message);
  }

  return response.json();
}

/**
 * Create a new RAG session.
 * @returns {Promise<{session_id: string, pdf_loaded: boolean, pdf_name: string|null, chunk_count: number}>}
 */
export async function createSession() {
  return request('/sessions', { method: 'POST' });
}

/**
 * Get session status.
 * @param {string} sessionId
 * @returns {Promise<{session_id: string, pdf_loaded: boolean, pdf_name: string|null, chunk_count: number}>}
 */
export async function getSession(sessionId) {
  return request(`/sessions/${sessionId}`);
}

/**
 * Upload and process a PDF file.
 * @param {string} sessionId
 * @param {File} file - The PDF file to upload
 * @param {function} onProgress - Optional progress callback
 * @returns {Promise<{message: string, chunk_count: number, pdf_name: string}>}
 */
export async function uploadPdf(sessionId, file, onProgress) {
  const formData = new FormData();
  formData.append('file', file);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    });

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        try {
          const error = JSON.parse(xhr.responseText);
          reject(new Error(error.detail || 'Upload failed'));
        } catch {
          reject(new Error('Upload failed'));
        }
      }
    });

    xhr.addEventListener('error', () => reject(new Error('Network error during upload')));
    xhr.addEventListener('abort', () => reject(new Error('Upload aborted')));

    xhr.open('POST', `${API_BASE}/sessions/${sessionId}/upload`);
    xhr.send(formData);
  });
}

/**
 * Ask a question about the loaded PDF.
 * @param {string} sessionId
 * @param {string} question
 * @returns {Promise<{answer: string, sources: Array}>}
 */
export async function askQuestion(sessionId, question) {
  return request(`/sessions/${sessionId}/ask`, {
    method: 'POST',
    body: JSON.stringify({ question }),
  });
}

/**
 * Clear a session.
 * @param {string} sessionId
 * @returns {Promise<{message: string}>}
 */
export async function clearSession(sessionId) {
  return request(`/sessions/${sessionId}`, { method: 'DELETE' });
}

/**
 * Health check.
 * @returns {Promise<{status: string}>}
 */
export async function healthCheck() {
  return request('/health');
}
