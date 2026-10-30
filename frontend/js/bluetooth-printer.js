/* Driver Web Bluetooth untuk printer thermal ESC/POS.
   Ref: PRD BAB 6 & FR-PRN-01 s/d FR-PRN-06. */
(function () {
  'use strict';

  const SERVICE_UUIDS = [
    '000018f0-0000-1000-8000-00805f9b34fb',
    '0000ffe0-0000-1000-8000-00805f9b34fb',
    '0000ff00-0000-1000-8000-00805f9b34fb',
    '0000ff10-0000-1000-8000-00805f9b34fb',
    '0000ff20-0000-1000-8000-00805f9b34fb',
  ];

  const CHUNK_SIZE = 50;
  const CHUNK_DELAY = 25;

  let device = null;
  let characteristic = null;
  const listeners = [];
  const status = { connected: false, connecting: false, name: null };

  function emit() {
    const snapshot = {
      connected: status.connected,
      connecting: status.connecting,
      name: status.name,
    };
    listeners.forEach((listener) => {
      try {
        listener(snapshot);
      } catch (err) {
        /* listener tidak boleh memutus alur printer */
      }
    });
  }

  function isSupported() {
    return typeof navigator !== 'undefined' && !!navigator.bluetooth;
  }

  function reset() {
    device = null;
    characteristic = null;
    status.connected = false;
    status.connecting = false;
    status.name = null;
    emit();
  }

  function handleDisconnect() {
    reset();
  }

  function base64ToBytes(base64) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes;
  }

  async function findWritableCharacteristic(server) {
    for (const uuid of SERVICE_UUIDS) {
      try {
        const service = await server.getPrimaryService(uuid);
        const chars = await service.getCharacteristics();
        const writable =
          chars.find((c) => c.properties.writeWithoutResponse) ||
          chars.find((c) => c.properties.write);
        if (writable) return writable;
      } catch (err) {
        /* lanjut ke UUID berikutnya */
      }
    }

    try {
      const services = await server.getPrimaryServices();
      for (const service of services) {
        try {
          const chars = await service.getCharacteristics();
          const writable =
            chars.find((c) => c.properties.writeWithoutResponse) ||
            chars.find((c) => c.properties.write);
          if (writable) return writable;
        } catch (err) {
          /* abaikan service tanpa karakteristik tulis */
        }
      }
    } catch (err) {
      return null;
    }
    return null;
  }

  async function connect() {
    if (!isSupported()) {
      throw new Error(
        'Browser tidak mendukung Web Bluetooth. Gunakan Chrome/Edge dan akses lewat localhost.'
      );
    }
    if (status.connected) return status;

    status.connecting = true;
    emit();

    try {
      device = await navigator.bluetooth.requestDevice({
        acceptAllDevices: true,
        optionalServices: SERVICE_UUIDS,
      });
      device.addEventListener('gattserverdisconnected', handleDisconnect);

      const server = await device.gatt.connect();
      characteristic = await findWritableCharacteristic(server);

      if (!characteristic) {
        throw new Error(
          'Karakteristik printer tidak ditemukan. Pastikan printer thermal ESC/POS aktif.'
        );
      }

      status.connected = true;
      status.name = device.name || 'Printer Thermal';
      return { connected: true, name: status.name };
    } catch (err) {
      if (device && device.gatt && device.gatt.connected) {
        try {
          device.gatt.disconnect();
        } catch (ignore) {
          /* noop */
        }
      }
      device = null;
      characteristic = null;
      status.connected = false;
      status.name = null;
      throw err;
    } finally {
      status.connecting = false;
      emit();
    }
  }

  function disconnect() {
    try {
      if (device && device.gatt && device.gatt.connected) device.gatt.disconnect();
    } catch (err) {
      /* noop */
    }
    reset();
  }

  async function writeBytes(bytes) {
    if (!characteristic) {
      throw new Error('Printer belum terhubung.');
    }

    for (let offset = 0; offset < bytes.length; offset += CHUNK_SIZE) {
      const chunk = bytes.slice(offset, offset + CHUNK_SIZE);
      let written = false;

      if (typeof characteristic.writeValueWithoutResponse === 'function') {
        try {
          await characteristic.writeValueWithoutResponse(chunk);
          written = true;
        } catch (err) {
          written = false;
        }
      }

      if (!written) {
        await characteristic.writeValue(chunk);
      }

      await new Promise((resolve) => setTimeout(resolve, CHUNK_DELAY));
    }
  }

  async function printBase64(base64) {
    if (!base64) throw new Error('Data struk kosong.');
    if (!status.connected) throw new Error('Hubungkan printer Bluetooth terlebih dahulu.');
    await writeBytes(base64ToBytes(base64));
  }

  function onChange(listener) {
    if (typeof listener !== 'function') return () => {};
    listeners.push(listener);
    listener({
      connected: status.connected,
      connecting: status.connecting,
      name: status.name,
    });
    return () => {
      const index = listeners.indexOf(listener);
      if (index >= 0) listeners.splice(index, 1);
    };
  }

  window.BluetoothPrinter = {
    isSupported,
    connect,
    disconnect,
    printBase64,
    onChange,
    get connected() {
      return status.connected;
    },
    get name() {
      return status.name;
    },
  };
})();
