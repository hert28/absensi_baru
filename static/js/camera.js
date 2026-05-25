/**
 * camera.js — Streaming kamera ke dashboard via WebSocket
 * Mengirim frame kamera ke server setiap 500ms untuk proses recognition
 */

// === State kamera ===
const CameraManager = {
    stream: null,           // MediaStream dari getUserMedia
    video: null,            // Element <video>
    canvas: null,           // Canvas untuk capture frame
    ctx: null,              // Canvas 2D context
    isActive: false,        // Status kamera aktif/tidak
    intervalId: null,       // Interval pengiriman frame
    socket: null,           // SocketIO connection
    frameInterval: 500,     // Kirim frame setiap 500ms
    lastResult: null,       // Hasil recognition terakhir

    /**
     * Inisialisasi kamera manager
     * Dipanggil saat halaman dashboard dimuat
     */
    init: function () {
        this.video = document.getElementById('camera-feed');
        this.canvas = document.createElement('canvas');
        this.ctx = this.canvas.getContext('2d');

        // Inisialisasi SocketIO
        this._initSocket();

        console.log('[CAMERA] Manager berhasil diinisialisasi.');
    },

    /**
     * Inisialisasi koneksi SocketIO
     */
    _initSocket: function () {
        // Gunakan SocketIO jika tersedia
        if (typeof io !== 'undefined') {
            this.socket = io({
                transports: ['websocket', 'polling'],
                reconnection: true,
                reconnectionDelay: 1000,
                reconnectionAttempts: 5
            });

            this.socket.on('connect', () => {
                console.log('[SOCKET] Terhubung ke server.');
                DashboardUI.updateConnectionStatus(true);
            });

            this.socket.on('disconnect', () => {
                console.log('[SOCKET] Terputus dari server.');
                DashboardUI.updateConnectionStatus(false);
            });

            // Terima hasil recognition dari server
            this.socket.on('recognition_result', (data) => {
                console.log('[SOCKET] recognition_result:', data);
                this._handleRecognitionResult(data);
            });

            // Terima update absensi baru (broadcast ke semua client)
            this.socket.on('absensi_update', (data) => {
                DashboardUI.addAbsensiRow(data);
                DashboardUI.updateStats(data.stats);
            });

            this.socket.on('connect_error', (err) => {
                console.warn('[SOCKET] Gagal terhubung:', err.message);
            });
        } else {
            console.warn('[CAMERA] SocketIO tidak tersedia, gunakan mode polling.');
        }
    },

    /**
     * Nyalakan kamera — akses webcam dan mulai stream
     */
    start: async function () {
        if (this.isActive) return;

        try {
            // Minta akses kamera
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    facingMode: 'user'
                },
                audio: false
            });

            // Tampilkan di video element
            this.video.srcObject = this.stream;
            this.video.classList.add('active');
            await this.video.play();

            // Set canvas ukuran sesuai video
            this.canvas.width = 640;
            this.canvas.height = 480;

            this.isActive = true;

            // Sembunyikan placeholder
            const placeholder = document.getElementById('camera-placeholder');
            if (placeholder) placeholder.classList.add('hidden');

            // Mulai kirim frame ke server
            this._startStreaming();

            // Beritahu server kamera ON
            if (this.socket && this.socket.connected) {
                this.socket.emit('camera_toggle', { active: true });
            }

            DashboardUI.updateCameraButtons(true);
            DashboardUI.showToast('success', 'Kamera Aktif', 'Face recognition dan anti-spoofing sedang berjalan.');

            console.log('[CAMERA] Kamera berhasil dinyalakan.');
        } catch (err) {
            console.error('[CAMERA] Gagal akses kamera:', err);
            DashboardUI.showToast('error', 'Gagal Akses Kamera',
                'Pastikan kamera terhubung dan izin diberikan.');
        }
    },

    /**
     * Matikan kamera — stop stream dan clear interval
     */
    stop: function () {
        if (!this.isActive) return;

        // Stop interval pengiriman frame
        this._stopStreaming();

        // Stop media stream
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }

        // Reset video element
        this.video.srcObject = null;
        this.video.classList.remove('active');

        this.isActive = false;

        // Tampilkan placeholder
        const placeholder = document.getElementById('camera-placeholder');
        if (placeholder) placeholder.classList.remove('hidden');

        // Beritahu server kamera OFF
        if (this.socket && this.socket.connected) {
            this.socket.emit('camera_toggle', { active: false });
        }

        // Sembunyikan overlay recognition
        DashboardUI.hideRecognitionOverlay();
        DashboardUI.updateCameraButtons(false);
        DashboardUI.showToast('info', 'Kamera Dimatikan', 'Streaming telah dihentikan.');

        console.log('[CAMERA] Kamera dimatikan.');
    },

    /**
     * Mulai streaming — capture dan kirim frame periodik
     */
    _startStreaming: function () {
        // Tampilkan processing indicator
        const indicator = document.getElementById('processing-indicator');
        if (indicator) indicator.classList.add('active');

        this.intervalId = setInterval(() => {
            if (!this.isActive || !this.video.videoWidth) return;
            this._captureAndSend();
        }, this.frameInterval);
    },

    /**
     * Stop streaming
     */
    _stopStreaming: function () {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }

        const indicator = document.getElementById('processing-indicator');
        if (indicator) indicator.classList.remove('active');
    },

    /**
     * Capture frame dari video dan kirim ke server
     */
    _captureAndSend: function () {
        // Gambar video ke canvas
        this.ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);

        // Konversi ke base64 JPEG (kompresi 85% — dinaikkan dari 70% agar
        // kualitas frame lebih mendekati foto training sehingga confidence LBPH lebih akurat)
        const frameData = this.canvas.toDataURL('image/jpeg', 0.85);

        // Kirim via SocketIO (lebih cepat dari HTTP)
        if (this.socket && this.socket.connected) {
            this.socket.emit('process_frame', { frame: frameData });
        } else {
            // Fallback: kirim via HTTP POST
            this._sendFrameHTTP(frameData);
        }
    },

    /**
     * Fallback: kirim frame via HTTP jika WebSocket tidak tersedia
     */
    _sendFrameHTTP: async function (frameData) {
        try {
            const response = await fetch('/api/absensi/proses', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ frame: frameData })
            });
            const result = await response.json();
            this._handleRecognitionResult(result);
        } catch (err) {
            console.warn('[CAMERA] Gagal kirim frame via HTTP:', err);
        }
    },

    /**
     * Handle hasil recognition dari server
     */
    _handleRecognitionResult: function (data) {
        this.lastResult = data;
        var indicatorSpan = document.querySelector('#processing-indicator span:last-child');

        // Skip — berbagai tipe
        if (data.status === 'skip') {
            if (data.tipe === 'verifying') {
                if (indicatorSpan) indicatorSpan.textContent = '🔍 ' + (data.pesan || 'Memverifikasi...');
            } else if (data.tipe === 'no_face') {
                if (indicatorSpan) indicatorSpan.textContent = 'Mencari wajah...';
            } else {
                if (indicatorSpan) indicatorSpan.textContent = 'Mencari wajah...';
            }
            return;
        }

        if (data.status === 'error') {
            // Spoofing terdeteksi
            if (data.tipe === 'spoofing') {
                if (indicatorSpan) indicatorSpan.textContent = '⚠️ Spoofing!';
                DashboardUI.showSpoofingWarning(data);
            } else if (data.tipe === 'duplikat') {
                if (indicatorSpan) indicatorSpan.textContent = '✓ Sudah absen';
                this._throttledToast('info', 'Sudah Absen', data.pesan || 'Mahasiswa sudah absen hari ini.');
            } else if (data.tipe === 'unknown') {
                if (indicatorSpan) indicatorSpan.textContent = '? Wajah tidak dikenali';
                this._throttledToast('warning', 'Tidak Dikenali', data.pesan || 'Wajah tidak cocok dengan database.');
            } else if (data.tipe === 'no_jadwal') {
                if (indicatorSpan) indicatorSpan.textContent = '⏰ Tidak ada jadwal';
                this._throttledToast('warning', 'Tidak Ada Jadwal', data.pesan || 'Tidak ada jadwal aktif saat ini.');
            } else {
                if (indicatorSpan) indicatorSpan.textContent = 'Memproses...';
                console.warn('[CAMERA] Recognition error:', data.pesan);
            }
            return;
        }

        if (data.status === 'ok') {
            if (indicatorSpan) indicatorSpan.textContent = '✓ ' + data.data.nama;
            // Wajah berhasil dikenali dan absensi dicatat
            DashboardUI.showRecognitionSuccess(data.data);
            DashboardUI.showToast('success', 'Absensi Tercatat',
                `${data.data.nama} — ${data.data.status_absensi}`);
            // Refresh tabel absensi
            DashboardUI.refreshAbsensiTable();
        }

        // Update spoofing indicator
        if (data.spoofing) {
            DashboardUI.updateSpoofingIndicator(data.spoofing);
        }
    },

    /**
     * Toast dengan throttle — agar tidak spam notifikasi berulang
     */
    _throttledToast: function (type, title, message) {
        var now = Date.now();
        var key = type + ':' + title;
        if (!this._toastTimers) this._toastTimers = {};
        if (this._toastTimers[key] && now - this._toastTimers[key] < 5000) return;
        this._toastTimers[key] = now;
        DashboardUI.showToast(type, title, message);
    }
};
