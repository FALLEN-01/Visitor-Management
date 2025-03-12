document.addEventListener('DOMContentLoaded', function() {
    // Database backup functionality
    const backupDbBtn = document.querySelector('.backup-action:nth-child(1) .backup-btn');
    if (backupDbBtn) {
        backupDbBtn.addEventListener('click', function() {
            // Show loading state
            const originalText = this.innerHTML;
            this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
            this.disabled = true;

            // Make AJAX request to backup API endpoint
            fetch('/admin/api/backup-database', {
                method: 'POST',
            })
            .then(response => {
                if (response.ok) return response.blob();
                throw new Error('Backup failed');
            })
            .then(blob => {
                // Create download link for the SQL file
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                const date = new Date().toISOString().slice(0, 10);
                a.download = `vms-backup-${date}.sql`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                
                // Show success message
                this.innerHTML = '<i class="fas fa-check"></i> Completed';
                setTimeout(() => {
                    this.innerHTML = originalText;
                    this.disabled = false;
                }, 2000);
            })
            .catch(error => {
                console.error('Error:', error);
                this.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Failed';
                setTimeout(() => {
                    this.innerHTML = originalText;
                    this.disabled = false;
                }, 2000);
            });
        });
    }

    // Export all logs functionality
    const exportLogsBtn = document.querySelector('.backup-action:nth-child(2) .backup-btn');
    if (exportLogsBtn) {
        exportLogsBtn.addEventListener('click', function() {
            // Show loading state
            const originalText = this.innerHTML;
            this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
            this.disabled = true;

            // Make AJAX request to export logs endpoint
            fetch('/admin/api/export-all-logs', {
                method: 'POST',
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(data => {
                        if (data.error && data.error.includes("openpyxl")) {
                            throw new Error("Missing Excel library. Please install openpyxl.");
                        } else {
                            throw new Error(data.error || 'Export failed');
                        }
                    });
                }
                return response.blob();
            })
            .then(blob => {
                // Create download link for the file
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                const date = new Date().toISOString().slice(0, 10);
                
                // Determine file extension from blob type
                let extension = 'xlsx';
                if (blob.type === 'text/csv') {
                    extension = 'csv';
                }
                
                a.download = `visitor-logs-${date}.${extension}`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                
                // Show success message
                this.innerHTML = '<i class="fas fa-check"></i> Completed';
                setTimeout(() => {
                    this.innerHTML = originalText;
                    this.disabled = false;
                }, 2000);
            })
            .catch(error => {
                console.error('Error:', error);
                
                // Show specific error message for missing openpyxl
                if (error.message && error.message.includes("openpyxl")) {
                    this.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Server missing Excel library';
                } else {
                    // Show general error with details if available
                    this.innerHTML = `<i class="fas fa-exclamation-triangle"></i> Failed: ${error.message ? error.message.substring(0, 20) + '...' : ''}`;
                }
                
                setTimeout(() => {
                    this.innerHTML = originalText;
                    this.disabled = false;
                }, 3000);
            });
        });
    }

    // Auto backup toggle functionality
    const autoBackupToggle = document.getElementById('auto-backup');
    if (autoBackupToggle) {
        autoBackupToggle.addEventListener('change', function() {
            fetch('/admin/api/set-auto-backup', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    enabled: this.checked
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Show success indicator
                    const parent = this.closest('.backup-action');
                    const indicator = document.createElement('span');
                    indicator.className = 'success-indicator';
                    indicator.innerHTML = '<i class="fas fa-check"></i> Saved';
                    indicator.style.color = '#2ecc71';
                    indicator.style.marginLeft = '10px';
                    parent.appendChild(indicator);
                    
                    setTimeout(() => {
                        parent.removeChild(indicator);
                    }, 2000);
                }
            })
            .catch(error => console.error('Error:', error));
        });
    }

    // Restore backup functionality
    const backupUpload = document.getElementById('backup-upload');
    if (backupUpload) {
        backupUpload.addEventListener('change', function() {
            if (!this.files || !this.files[0]) return;
            
            const file = this.files[0];
            const fileUploadText = document.querySelector('.file-upload-text');
            fileUploadText.textContent = file.name;
            
            // Create restore button if it doesn't exist
            let restoreBtn = document.getElementById('restore-backup-btn');
            if (!restoreBtn) {
                restoreBtn = document.createElement('button');
                restoreBtn.id = 'restore-backup-btn';
                restoreBtn.className = 'btn-primary';
                restoreBtn.innerHTML = '<i class="fas fa-upload"></i> Restore';
                restoreBtn.style.marginTop = '10px';
                
                const wrapper = this.closest('.file-upload-wrapper');
                wrapper.parentNode.appendChild(restoreBtn);
                
                // Add click handler for restore
                restoreBtn.addEventListener('click', function() {
                    const formData = new FormData();
                    formData.append('backup_file', file);
                    
                    // Show loading state
                    const originalText = this.innerHTML;
                    this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Restoring...';
                    this.disabled = true;
                    
                    fetch('/admin/api/restore-backup', {
                        method: 'POST',
                        body: formData
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            this.innerHTML = '<i class="fas fa-check"></i> Restored';
                        } else {
                            this.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Failed';
                        }
                        
                        setTimeout(() => {
                            this.innerHTML = originalText;
                            this.disabled = false;
                        }, 2000);
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        this.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Failed';
                        setTimeout(() => {
                            this.innerHTML = originalText;
                            this.disabled = false;
                        }, 2000);
                    });
                });
            }
        });
    }
});