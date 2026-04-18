export function createSocket(onMessage, onOpen, onClose) {
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${protocol}://${location.host}`);
  ws.addEventListener('open', () => onOpen?.());
  ws.addEventListener('close', () => onClose?.());
  ws.addEventListener('message', (event) => onMessage(JSON.parse(event.data)));
  return ws;
}
