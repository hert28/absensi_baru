/**
 * dashboard.js — Logic tombol ON/OFF kamera, update real-time tabel absensi
 * Mengontrol UI dashboard dan menampilkan hasil recognition
 */

const DashboardUI = {
    /**
     * Inisialisasi event listener dan UI dashboard
     */
    init: function () {
        // Tombol kontrol kamera
        const btnOn = document.getElementById('btn-camera-on');
        const btnOff = document.getElementById('btn-camera-off');

        if (btnOn) {
            btnOn.addEventListener('click', () => CameraManager.start());
        }
        if (btnOff) {
            btnOff.addEventListener('click', () => CameraManager.stop());
        }

        // Auto-refresh absensi hari ini setiap 30 detik
        setInterval(() => this.refreshAbsensiTable(), 30000);

        console.log('[DASHBOARD] UI berhasil diinisialisasi.');
    },

    /**
     * Update tampilan tombol kamera berdasarkan status
     */
    updateCameraButtons: function (isActive) {
        const btnOn = document.getElementById('btn-camera-on');
        const btnOff = document.getElementById('btn-camera-off');

        if (isActive) {
            if (btnOn) btnOn.style.display = 'none';
            if (btnOff) btnOff.style.display = 'flex';
        } else {
            if (btnOn) btnOn.style.display = 'flex';
            if (btnOff) btnOff.style.display = 'none';
        }
    },

    /**
     * Update indikator koneksi WebSocket
     */
    updateConnectionStatus: function (connected) {
        const indicator = document.getElementById('connection-status');
        if (!indicator) return;

        if (connected) {
            indicator.textContent = 'Terhubung';
            indicator.classList.remove('text-error');
            indicator.classList.add('text-emerald-500');
        } else {
            indicator.textContent = 'Terputus';
            indicator.classList.remove('text-emerald-500');
            indicator.classList.add('text-error');
        }
    },

    /**
     * Update indikator anti-spoofing
     */
    updateSpoofingIndicator: function (spoofData) {
        const indicator = document.getElementById('spoofing-indicator');
        if (!indicator) return;

        if (spoofData.is_real) {
            indicator.className = 'active';
            indicator.querySelector('.dot').style.background = '#34d399';
            indicator.querySelector('.label').textContent = 'Anti-Spoofing: OK';
        } else {
            indicator.className = 'warning';
            indicator.querySelector('.dot').style.background = '#f87171';
            indicator.querySelector('.label').textContent = 'SPOOFING!';
        }
    },

    /**
     * Tampilkan peringatan spoofing
     */
    showSpoofingWarning: function (data) {
        const overlay = document.getElementById('recognition-overlay');
        if (!overlay) return;

        overlay.innerHTML = `
            <div class="flex items-center gap-3">
                <span class="material-symbols-outlined text-3xl text-error">gpp_bad</span>
                <div>
                    <p class="recognition-name text-error">⚠️ Spoofing Terdeteksi!</p>
                    <p class="recognition-detail">Score: ${data.score || '-'} — Wajah tidak asli</p>
                </div>
            </div>
        `;
        overlay.classList.add('active');

        // Sembunyikan setelah 3 detik
        setTimeout(() => overlay.classList.remove('active'), 3000);

        this.showToast('error', 'Spoofing Terdeteksi',
            'Sistem mendeteksi percobaan spoofing. Gunakan wajah asli.');
    },

    /**
     * Tampilkan hasil recognition berhasil di overlay — mendukung multi-face.
     * Menerima array data sehingga semua wajah yang berhasil ditampilkan sekaligus.
     * @param {Array|Object} dataOrList — satu data object atau array data objects
     */
    showRecognitionSuccess: function (dataOrList) {
        const overlay = document.getElementById('recognition-overlay');
        if (!overlay) return;

        // Normalisasi ke array agar kompatibel dengan pemanggilan lama (single) & baru (batch)
        const list = Array.isArray(dataOrList) ? dataOrList : [dataOrList];

        // Bersihkan overlay lama, lalu bangun ulang dengan semua wajah
        overlay.innerHTML = '';

        list.forEach(function(data) {
            const statusClass = data.status_absensi === 'hadir' ? 'hadir' : 'terlambat';
            const statusLabel = data.status_absensi === 'hadir' ? 'HADIR' : 'TERLAMBAT';
            const statusIcon = data.status_absensi === 'hadir' ? 'check_circle' : 'schedule';

            const entry = document.createElement('div');
            entry.className = 'recognition-entry';
            entry.innerHTML = `
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-3">
                        <span class="material-symbols-outlined text-2xl text-emerald-400">face</span>
                        <div>
                            <p class="recognition-name">${data.nama}</p>
                            <p class="recognition-detail">${data.nim} — ${data.nama_kelas || ''} — ${data.nama_mk || ''}</p>
                        </div>
                    </div>
                    <span class="status-badge ${statusClass}">
                        <span class="material-symbols-outlined" style="font-size:14px">${statusIcon}</span>
                        ${statusLabel}
                    </span>
                </div>
            `;
            overlay.appendChild(entry);
        });

        overlay.classList.add('active');

        // Sembunyikan setelah 5 detik (reset timer jika dipanggil ulang)
        if (this._overlayTimer) clearTimeout(this._overlayTimer);
        this._overlayTimer = setTimeout(function() { overlay.classList.remove('active'); }, 5000);
    },

    /**
     * Sembunyikan overlay recognition
     */
    hideRecognitionOverlay: function () {
        const overlay = document.getElementById('recognition-overlay');
        if (overlay) overlay.classList.remove('active');
    },

    /**
     * Tambahkan baris baru ke tabel absensi hari ini
     */
    addAbsensiRow: function (data) {
        const tbody = document.getElementById('absensi-tbody');
        if (!tbody) return;

        // Hapus pesan "belum ada absensi" jika ada
        const emptyRow = tbody.querySelector('.empty-row');
        if (emptyRow) emptyRow.remove();

        // Buat baris baru
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-surface-container-high transition-colors absensi-row-new';

        // Tentukan badge status
        let badgeClass, badgeLabel;
        switch (data.status) {
            case 'hadir':
                badgeClass = 'bg-emerald-500/15 text-emerald-500';
                badgeLabel = 'Hadir';
                break;
            case 'terlambat':
                badgeClass = 'bg-tertiary/15 text-tertiary';
                badgeLabel = 'Terlambat';
                break;
            case 'alpha':
                badgeClass = 'bg-error/15 text-error';
                badgeLabel = 'Alpha';
                break;
            default:
                badgeClass = 'bg-secondary/15 text-secondary';
                badgeLabel = data.status;
        }

        tr.innerHTML = `
            <td class="px-6 py-4">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-full bg-secondary-container flex items-center justify-center">
                        <span class="material-symbols-outlined text-secondary text-[20px]">person</span>
                    </div>
                    <div>
                        <p class="font-body-md text-on-surface font-semibold">${data.nama}</p>
                        <p class="text-[12px] text-on-surface-variant">${data.nim} — ${data.nama_kelas || ''}</p>
                    </div>
                </div>
            </td>
            <td class="px-6 py-4 text-body-sm text-on-surface-variant">${data.waktu_absen || '-'}</td>
            <td class="px-6 py-4">
                <span class="px-3 py-1 rounded-full ${badgeClass} text-[12px] font-bold">${badgeLabel}</span>
            </td>
        `;

        // Sisipkan di posisi pertama
        tbody.insertBefore(tr, tbody.firstChild);
    },

    /**
     * Update statistik card di dashboard
     */
    updateStats: function (stats) {
        if (!stats) return;

        const hadirEl = document.getElementById('stat-hadir');
        const terlambatEl = document.getElementById('stat-terlambat');
        const alphaEl = document.getElementById('stat-alpha');

        if (hadirEl && stats.hadir !== undefined) hadirEl.textContent = stats.hadir;
        if (terlambatEl && stats.terlambat !== undefined) terlambatEl.textContent = stats.terlambat;
        if (alphaEl && stats.alpha !== undefined) alphaEl.textContent = stats.alpha;
    },

    /**
     * Refresh tabel absensi dari server (polling fallback)
     */
    refreshAbsensiTable: async function () {
        try {
            const response = await fetch('/api/absensi/hari-ini');
            const result = await response.json();

            if (result.status === 'ok' && result.data) {
                const tbody = document.getElementById('absensi-tbody');
                if (!tbody) return;

                // Rebuild tabel hanya jika ada perubahan
                const currentCount = tbody.querySelectorAll('tr:not(.empty-row)').length;
                if (result.data.length !== currentCount) {
                    tbody.innerHTML = '';
                    if (result.data.length === 0) {
                        tbody.innerHTML = `
                            <tr class="empty-row">
                                <td colspan="3" class="px-6 py-12 text-center">
                                    <span class="material-symbols-outlined text-3xl text-on-surface-variant/20 mb-2">event_busy</span>
                                    <p class="text-body-sm text-on-surface-variant">Belum ada absensi hari ini</p>
                                </td>
                            </tr>
                        `;
                    } else {
                        result.data.forEach(a => this.addAbsensiRow(a));
                    }
                }
            }
        } catch (err) {
            console.warn('[DASHBOARD] Gagal refresh absensi:', err);
        }
    },

    /**
     * Tampilkan toast notification
     */
    showToast: function (type, title, message) {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            document.body.appendChild(container);
        }

        // Icon per tipe
        const icons = {
            success: 'check_circle',
            error: 'error',
            warning: 'warning',
            info: 'info'
        };

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <span class="material-symbols-outlined toast-icon">${icons[type] || 'info'}</span>
            <div class="toast-body">
                <div class="toast-title">${title}</div>
                <div class="toast-message">${message}</div>
            </div>
        `;

        container.appendChild(toast);

        // Auto-hapus setelah 4 detik
        setTimeout(() => {
            toast.classList.add('removing');
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }
};

// === Inisialisasi saat DOM ready ===
document.addEventListener('DOMContentLoaded', () => {
    // Inisialisasi CameraManager
    if (typeof CameraManager !== 'undefined') {
        CameraManager.init();
    }

    // Inisialisasi DashboardUI
    DashboardUI.init();

    // Sembunyikan tombol OFF secara default
    const btnOff = document.getElementById('btn-camera-off');
    if (btnOff) btnOff.style.display = 'none';
});
