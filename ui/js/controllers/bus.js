export const bus = new EventTarget();

export function emit(type, detail) {
  bus.dispatchEvent(new CustomEvent(type, { detail }));
}

export function on(type, fn) {
  const handler = (event) => fn(event.detail, event);
  bus.addEventListener(type, handler);
  return () => bus.removeEventListener(type, handler);
}
