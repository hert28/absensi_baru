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
    isProcessing: false,    // Pengunci: frame baru hanya dikirim setelah server menjawab
    intervalId: null,       // Interval pengiriman frame
    socket: null,           // SocketIO connection
    frameInterval: 800,     // Kirim frame setiap 800ms (dinaikkan dari 500ms)
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
                    width:  { ideal: 640, max: 1280 },
                    height: { ideal: 480, max: 720 },
                    facingMode: 'user'
                },
                audio: false
            });

            // Tampilkan di video element
            this.video.srcObject = this.stream;
            this.video.classList.add('active');
            await this.video.play();

            // Canvas untuk capture (kecil = lebih cepat dikirim & diproses server)
            // Video tetap ditampilkan di resolusi aslinya ke user
            this.canvas.width  = 320;
            this.canvas.height = 240;

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
            // Pengunci: skip frame jika server belum menjawab request sebelumnya
            if (this.isProcessing) {
                console.log('[CAMERA] Frame skipped — menunggu respons server.');
                return;
            }
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

        // Kompresi JPEG 65% — cukup untuk LBPH, payload lebih kecil = lebih cepat
        const frameData = this.canvas.toDataURL('image/jpeg', 0.65);

        // Aktifkan pengunci sebelum kirim — dilepas di _handleRecognitionResult
        this.isProcessing = true;

        // Kirim via SocketIO (lebih cepat dari HTTP)
        if (this.socket && this.socket.connected) {
            this.socket.emit('process_frame', { frame: frameData });
        } else {
            // Fallback: kirim via HTTP POST
            this._sendFrameHTTP(frameData);
        }

        // Timeout pengaman: lepas kunci setelah 5 detik jika server tidak menjawab
        setTimeout(() => {
            if (this.isProcessing) {
                console.warn('[CAMERA] Timeout 5s — melepas kunci isProcessing.');
                this.isProcessing = false;
            }
        }, 5000);
    },

    /**
     * Fallback: kirim frame via HTTP jika WebSocket tidak tersedia
     * Menangani response batch {results: [...]} dari /api/absensi/proses
     */
    _sendFrameHTTP: async function (frameData) {
        try {
            const response = await fetch('/api/absensi/proses', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ frame: frameData })
            });
            const result = await response.json();
            // Format batch: {results: [...]}
            this._handleRecognitionResult(result);
        } catch (err) {
            console.warn('[CAMERA] Gagal kirim frame via HTTP:', err);
            this.isProcessing = false;
        }
    },

    /**
     * Handle hasil recognition BATCH dari server.
     * Menerima {results: [...]} — satu event berisi SEMUA wajah yang diproses.
     * Mengkategorikan semua hasil lalu menampilkan overlay & toast gabungan sekaligus.
     */
    _handleRecognitionResult: function (data) {
        // Lepas kunci — server sudah menjawab, frame berikutnya boleh dikirim
        this.isProcessing = false;

        // Ambil array hasil (format batch: {results: [...]})
        var results = data.results || [data];
        this.lastResult = results;

        var indicatorSpan = document.querySelector('#processing-indicator span:last-child');

        // Update spoofing indicator dari hasil yang punya info spoofing
        for (var i = 0; i < results.length; i++) {
            if (results[i].spoofing) {
                DashboardUI.updateSpoofingIndicator(results[i].spoofing);
                break;
            }
        }

        // ── Kategorikan semua hasil sekaligus ──
        var sukses = [];
        var verifying = [];
        var duplikat = [];
        var noJadwal = [];
        var unknown = [];
        var spoofing = null;
        var noFace = false;

        for (var i = 0; i < results.length; i++) {
            var item = results[i];
            if (item.status === 'ok') {
                sukses.push(item);
            } else if (item.status === 'skip') {
                if (item.tipe === 'verifying') verifying.push(item);
                else if (item.tipe === 'no_face') noFace = true;
            } else if (item.status === 'error') {
                if (item.tipe === 'spoofing') spoofing = item;
                else if (item.tipe === 'duplikat') duplikat.push(item);
                else if (item.tipe === 'unknown') unknown.push(item);
                else if (item.tipe === 'no_jadwal') noJadwal.push(item);
            }
        }

        // ── Spoofing — prioritas tertinggi, langsung return ──
        if (spoofing) {
            if (indicatorSpan) indicatorSpan.textContent = '⚠️ Spoofing!';
            DashboardUI.showSpoofingWarning(spoofing);
            return;
        }

        // ── Absensi berhasil — tampilkan SEMUA wajah sekaligus ──
        if (sukses.length > 0) {
            var dataList = sukses.map(function(s) { return s.data; });
            var names = dataList.map(function(d) { return d ? d.nama : '?'; });
            if (indicatorSpan) indicatorSpan.textContent = '✓ ' + names.join(', ');

            // Tampilkan overlay multi-face sekaligus
            DashboardUI.showRecognitionSuccess(dataList);

            // Toast gabungan: 1 notifikasi untuk semua wajah yang berhasil
            var namaLines = dataList.map(function(d) {
                var statusLabel = d.status_absensi === 'hadir' ? 'Hadir' : 'Terlambat';
                return d.nama + ' — ' + statusLabel;
            });
            var toastTitle = sukses.length > 1
                ? 'Absensi Tercatat (' + sukses.length + ' orang)'
                : 'Absensi Tercatat';
            DashboardUI.showToast('success', toastTitle, namaLines.join(' • '));

            DashboardUI.refreshAbsensiTable();
        }

        // ── Verifikasi wajah (belum cukup frame konsekutif) ──
        if (verifying.length > 0 && sukses.length === 0) {
            var verifMsg = verifying.length === 1
                ? (verifying[0].pesan || 'Memverifikasi...')
                : 'Memverifikasi ' + verifying.length + ' wajah...';
            if (indicatorSpan) indicatorSpan.textContent = '🔍 ' + verifMsg;
        }

        // ── Duplikat — sudah absen sebelumnya ──
        if (duplikat.length > 0) {
            if (indicatorSpan && sukses.length === 0 && verifying.length === 0) {
                indicatorSpan.textContent = '✓ Sudah absen';
            }
            var dupNames = duplikat.map(function(d) {
                return d.data ? d.data.nama : '';
            }).filter(Boolean);
            if (dupNames.length > 0) {
                var dupMsg = dupNames.length > 1
                    ? dupNames.join(', ') + ' sudah absen hari ini.'
                    : dupNames[0] + ' sudah absen hari ini.';
                this._throttledToast('info', 'Sudah Absen', dupMsg);
            }
        }

        // ── Wajah tidak dikenali ──
        if (unknown.length > 0 && sukses.length === 0 && verifying.length === 0 && duplikat.length === 0) {
            if (indicatorSpan) indicatorSpan.textContent = '? Wajah tidak dikenali';
            var unknownMsg = unknown.length > 1
                ? unknown.length + ' wajah tidak cocok dengan database.'
                : 'Wajah tidak cocok dengan database.';
            this._throttledToast('warning', 'Tidak Dikenali', unknownMsg);
        }

        // ── Tidak ada jadwal aktif ──
        if (noJadwal.length > 0 && sukses.length === 0 && verifying.length === 0) {
            if (indicatorSpan && duplikat.length === 0) {
                indicatorSpan.textContent = '⏰ Tidak ada jadwal';
            }
            var njNames = noJadwal.map(function(d) {
                return d.data ? d.data.nama : '';
            }).filter(Boolean);
            if (njNames.length > 0) {
                this._throttledToast('warning', 'Tidak Ada Jadwal',
                    'Tidak ada jadwal aktif untuk ' + njNames.join(', ') + '.');
            }
        }

        // ── Tidak ada wajah sama sekali ──
        if (noFace && sukses.length === 0 && verifying.length === 0 &&
            duplikat.length === 0 && unknown.length === 0) {
            if (indicatorSpan) indicatorSpan.textContent = 'Mencari wajah...';
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
