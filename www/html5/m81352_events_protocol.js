/* events-v1 transport: C60012 (u16 JSON) -> S60013 (u32 JSON). The server
 * builds every event view; this module only frames and validates JSON. */
import {Writer} from './protocol.js';
import {encodeFrame} from './sixcube.js';

export const EVENTS_REQUEST = 60012, EVENTS_REPLY = 60013;
const id = value => typeof value === 'string' && /^[A-Za-z0-9_-]{1,64}$/.test(value);
const key = value => typeof value === 'string' && /^[A-Za-z0-9_.:-]{0,64}$/.test(value);

export function encodeEventsRequest(action, request_id, values = {}) {
  if (!['list', 'act'].includes(action) || !id(request_id)) throw new RangeError('Yêu cầu sự kiện không hợp lệ.');
  const data = {v: 1, request_id, action};
  if (action === 'act') {
    if (!Number.isSafeInteger(values.event) || !key(values.op) || !key(values.key ?? ''))
      throw new RangeError('Thao tác sự kiện không hợp lệ.');
    Object.assign(data, {event: values.event, op: values.op, key: values.key ?? ''});
  }
  return encodeFrame(EVENTS_REQUEST, new Writer().string(JSON.stringify(data)).finish());
}

export function decodeEventsPacket({msgId, payload}) {
  if (msgId !== EVENTS_REPLY) return null;
  const bytes = payload instanceof Uint8Array ? payload : new Uint8Array(payload);
  if (bytes.length < 4) throw new RangeError('Gói sự kiện bị cắt.');
  const size = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getUint32(0, true);
  if (size !== bytes.length - 4) throw new RangeError('Độ dài gói sự kiện không khớp.');
  const reply = JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(bytes.subarray(4)));
  if (reply?.v !== 1 || typeof reply.ok !== 'boolean') throw new RangeError('Gói sự kiện không đúng phiên bản.');
  return {msgId, type: 'eventsReply', reply, byteLength: bytes.length, decodedBytes: bytes.length, tail: new Uint8Array(0), trailingBytes: 0};
}
