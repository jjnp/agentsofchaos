import { createOption, formatEvent } from './dom.js';

export class CardManager {
  constructor(gridEl, templateEl, sendMessage) {
    this.gridEl = gridEl;
    this.templateEl = templateEl;
    this.sendMessage = sendMessage;
    this.cards = new Map();
  }

  activeSlots() {
    return [...this.cards.keys()].sort((a, b) => a - b);
  }

  has(slot) {
    return this.cards.has(slot);
  }

  create(slot) {
    if (this.cards.has(slot)) return this.cards.get(slot);

    const fragment = this.templateEl.content.cloneNode(true);
    const article = fragment.querySelector('.card');
    const title = fragment.querySelector('.title');
    const meta = fragment.querySelector('.slot-meta');
    const terminal = fragment.querySelector('.terminal');
    const prompt = fragment.querySelector('.prompt');
    const send = fragment.querySelector('.send');
    const forkBtn = fragment.querySelector('.fork');
    const stopBtn = fragment.querySelector('.stop');
    const mergeTarget = fragment.querySelector('.mergeTarget');
    const bundleBtn = fragment.querySelector('.bundle');
    const mergeBtn = fragment.querySelector('.merge');
    const eventBox = fragment.querySelector('.event-box');

    title.textContent = `Instance ${slot + 1}`;
    meta.textContent = 'starting';
    article.dataset.slot = String(slot);

    send.addEventListener('click', () => {
      const message = prompt.value.trim();
      if (!message) return;
      this.sendMessage({ type: 'prompt', target: slot, message });
    });

    forkBtn.addEventListener('click', () => {
      this.sendMessage({ type: 'fork', source: slot });
    });

    stopBtn.addEventListener('click', () => {
      this.sendMessage({ type: 'stop_instance', target: slot });
    });

    bundleBtn.addEventListener('click', () => {
      if (!mergeTarget.value) return;
      this.sendMessage({ type: 'prepare_merge', source: slot, target: Number(mergeTarget.value) });
    });

    mergeBtn.addEventListener('click', () => {
      if (!mergeTarget.value) return;
      this.sendMessage({ type: 'merge', source: slot, target: Number(mergeTarget.value) });
    });

    this.gridEl.appendChild(fragment);

    const card = { article, meta, terminal, prompt, mergeTarget, eventBox, events: [] };
    this.cards.set(slot, card);
    this.refreshMergeTargets();
    return card;
  }

  remove(slot) {
    const card = this.cards.get(slot);
    if (!card) return;
    card.article.remove();
    this.cards.delete(slot);
    this.refreshMergeTargets();
  }

  refreshMergeTargets() {
    const slots = this.activeSlots();
    for (const [slot, card] of this.cards.entries()) {
      const previous = card.mergeTarget.value;
      card.mergeTarget.innerHTML = '';
      for (const other of slots) {
        if (other === slot) continue;
        card.mergeTarget.appendChild(createOption(other, `Instance ${other + 1}`));
      }
      if (card.mergeTarget.options.length === 0) {
        card.mergeTarget.appendChild(createOption('', 'No targets'));
        card.mergeTarget.disabled = true;
      } else {
        card.mergeTarget.disabled = false;
        if ([...card.mergeTarget.options].some((option) => option.value === previous)) {
          card.mergeTarget.value = previous;
        }
      }
    }
  }

  appendTerminal(slot, text) {
    const card = this.cards.get(slot);
    if (!card || !text) return;
    card.terminal.textContent += text;
    card.terminal.scrollTop = card.terminal.scrollHeight;
  }

  pushEvent(slot, payload) {
    const card = this.cards.get(slot);
    if (!card) return;
    card.events.unshift(formatEvent(payload));
    card.eventBox.textContent = card.events.slice(0, 6).join('\n\n');
  }

  setMeta(slot, text) {
    const card = this.cards.get(slot);
    if (card) card.meta.textContent = text;
  }
}
