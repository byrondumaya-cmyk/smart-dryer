// src/lib/firestore.js — Firestore Helpers (read-only listeners + command writes)
import {
  doc, collection,
  onSnapshot, addDoc, setDoc,
  serverTimestamp, query, orderBy, limit,
} from 'firebase/firestore';
import { db } from './firebase';

// ── Real-time listeners ───────────────────────────────────────────────────────

export function subscribeToStatus(callback) {
  return onSnapshot(doc(db, 'system', 'status'), (snap) => {
    callback(snap.exists() ? snap.data() : null);
  });
}

export function subscribeToConfig(callback) {
  return onSnapshot(doc(db, 'system', 'config'), (snap) => {
    callback(snap.exists() ? snap.data() : null);
  });
}

export function subscribeToSensors(callback) {
  return onSnapshot(doc(db, 'system', 'sensors'), (snap) => {
    callback(snap.exists() ? snap.data() : null);
  });
}

export function subscribeToSlots(callback) {
  return onSnapshot(doc(db, 'system', 'slots'), (snap) => {
    callback(snap.exists() ? snap.data() : null);
  });
}

export function subscribeScanHistory(callback, maxEntries = 50) {
  const q = query(
    collection(db, 'scan_history'),
    orderBy('timestamp', 'desc'),
    limit(maxEntries)
  );
  return onSnapshot(q, (snap) => {
    callback(snap.docs.map((d) => ({ id: d.id, ...d.data() })));
  });
}

// ── Command dispatcher ────────────────────────────────────────────────────────
// Dashboard writes commands; RPI polls, executes, and marks done.

export async function sendCommand(type, payload = {}) {
  return addDoc(collection(db, 'commands'), {
    type,
    payload,
    status:       'pending',
    created_at:   serverTimestamp(),
    processed_at: null,
  });
}

// ── Config mutation ───────────────────────────────────────────────────────────
// For fields the dashboard can update optimistically (interval, sms_recipient).

export async function updateConfig(fields) {
  return setDoc(
    doc(db, 'system', 'config'),
    { ...fields, updated_at: serverTimestamp() },
    { merge: true }
  );
}
