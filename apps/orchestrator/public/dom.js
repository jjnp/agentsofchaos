export function qs(id) {
  return document.getElementById(id);
}

export function createOption(value, text) {
  const option = document.createElement('option');
  option.value = String(value);
  option.textContent = text;
  return option;
}

export function formatEvent(payload) {
  return JSON.stringify(payload, null, 2);
}
