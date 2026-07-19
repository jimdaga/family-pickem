/* Progressive enhancement only: the native file remains the only upload. */
(function () {
    'use strict';
    var REMOVE_CONFIRMATION = 'Remove family logo? Your family will use the default logo after you save settings.';

    function ready(callback) {
        if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', callback); }
        else { callback(); }
    }

    ready(function () {
        var form = document.querySelector('[data-family-logo-form]');
        var input = document.getElementById('id_logo');
        var preview = document.querySelector('[data-family-logo-editor]');
        var serverPreview = document.querySelector('[data-family-logo-server-preview]');
        var adjust = document.querySelector('[data-family-logo-adjust]');
        var fullImage = document.querySelector('[data-family-logo-full-image]');
        var clear = document.querySelector('[data-family-logo-clear]');
        var remove = document.querySelector('[data-family-logo-remove]');
        var removeField = document.getElementById('id_remove_logo');
        var fields = ['crop_x', 'crop_y', 'crop_width', 'crop_height'].map(function (name) {
            return document.getElementById('id_' + name);
        });
        if (!form || !input || !preview || !serverPreview || !adjust || !fullImage || !clear || !removeField || !window.URL || !window.customElements || !window.customElements.get('cropper-canvas')) { return; }

        var objectUrl = null;
        var cropperImage = null;
        var cropperSelection = null;
        var cropActive = false;
        var serverImage = serverPreview.querySelector('img');
        var savedSource = serverImage && serverImage.getAttribute('src');
        var savedAlt = serverImage && serverImage.getAttribute('alt');
        var defaultSource = serverPreview.getAttribute('data-family-logo-default-src');

        function clearCropFields() { fields.forEach(function (field) { if (field) { field.value = ''; } }); }
        function restoreServerPreview() {
            if (serverImage && savedSource) { serverImage.setAttribute('src', savedSource); serverImage.setAttribute('alt', savedAlt || 'Family logo'); }
        }
        function emptyPreview(revokeUrl) {
            while (preview.firstChild) { preview.removeChild(preview.firstChild); }
            preview.classList.add('hidden'); preview.classList.remove('flex', 'p-0'); preview.classList.add('p-3');
            cropperImage = null; cropperSelection = null; cropActive = false;
            if (revokeUrl && objectUrl) { window.URL.revokeObjectURL(objectUrl); objectUrl = null; }
        }
        function showContainedPreview() {
            emptyPreview(false);
            var image = document.createElement('img');
            image.src = objectUrl; image.alt = 'Selected family logo preview'; image.className = 'max-h-full max-w-full object-contain';
            preview.appendChild(image); preview.classList.remove('hidden'); preview.classList.add('flex');
            serverPreview.classList.add('hidden'); adjust.classList.remove('hidden'); fullImage.classList.add('hidden'); clear.classList.remove('hidden');
            clearCropFields();
        }
        function selectionToSourcePixels() {
            if (!cropperImage || !cropperSelection) { clearCropFields(); return; }
            var selectionRect = cropperSelection.getBoundingClientRect();
            var imageRect = cropperImage.getBoundingClientRect();
            var naturalWidth = cropperImage.$image && cropperImage.$image.naturalWidth;
            var naturalHeight = cropperImage.$image && cropperImage.$image.naturalHeight;
            if (!naturalWidth || !naturalHeight || !imageRect.width || !imageRect.height) { clearCropFields(); return; }
            var x = Math.max(0, Math.round((selectionRect.left - imageRect.left) * naturalWidth / imageRect.width));
            var y = Math.max(0, Math.round((selectionRect.top - imageRect.top) * naturalHeight / imageRect.height));
            var side = Math.round(Math.min(selectionRect.width * naturalWidth / imageRect.width, selectionRect.height * naturalHeight / imageRect.height));
            side = Math.min(side, naturalWidth - x, naturalHeight - y);
            if (!Number.isSafeInteger(x) || !Number.isSafeInteger(y) || !Number.isSafeInteger(side) || side <= 0) { clearCropFields(); return; }
            fields[0].value = String(x); fields[1].value = String(y); fields[2].value = String(side); fields[3].value = String(side);
        }
        function showCropper() {
            emptyPreview(false);
            preview.classList.remove('hidden', 'p-3'); preview.classList.add('flex', 'p-0'); serverPreview.classList.add('hidden');
            var canvas = document.createElement('cropper-canvas'); canvas.setAttribute('background', ''); canvas.style.width = '100%'; canvas.style.height = '100%';
            var image = document.createElement('cropper-image'); image.setAttribute('translatable', ''); image.setAttribute('scalable', ''); image.setAttribute('src', objectUrl); image.setAttribute('alt', 'Adjust family logo framing');
            var shade = document.createElement('cropper-shade');
            var selection = document.createElement('cropper-selection'); selection.setAttribute('initial-coverage', '0.7'); selection.setAttribute('aspect-ratio', '1'); selection.setAttribute('initial-aspect-ratio', '1'); selection.setAttribute('movable', ''); selection.setAttribute('resizable', '');
            var grid = document.createElement('cropper-grid'); grid.setAttribute('role', 'grid'); grid.setAttribute('bordered', ''); grid.setAttribute('covered', '');
            selection.appendChild(grid);
            var move = document.createElement('cropper-handle'); move.setAttribute('action', 'move'); move.setAttribute('theme-color', 'rgba(255, 255, 255, 0.35)'); selection.appendChild(move);
            ['n', 'e', 's', 'w', 'ne', 'nw', 'se', 'sw'].forEach(function (direction) { var handle = document.createElement('cropper-handle'); handle.setAttribute('action', direction + '-resize'); selection.appendChild(handle); });
            canvas.appendChild(image); canvas.appendChild(shade); canvas.appendChild(selection); preview.appendChild(canvas);
            cropperImage = image; cropperSelection = selection; cropActive = true; adjust.classList.add('hidden'); fullImage.classList.remove('hidden');
            selection.addEventListener('change', function () { window.requestAnimationFrame(selectionToSourcePixels); });
            image.$ready(function () { image.$center('cover'); window.requestAnimationFrame(selectionToSourcePixels); }).catch(clearCropFields);
        }
        input.addEventListener('change', function () {
            var file = input.files && input.files[0];
            if (!file) { emptyPreview(true); restoreServerPreview(); clearCropFields(); removeField.value = ''; adjust.classList.add('hidden'); fullImage.classList.add('hidden'); clear.classList.add('hidden'); return; }
            emptyPreview(true); objectUrl = window.URL.createObjectURL(file); removeField.value = ''; showContainedPreview();
        });
        adjust.addEventListener('click', showCropper);
        fullImage.addEventListener('click', showContainedPreview);
        clear.addEventListener('click', function () { input.value = ''; emptyPreview(true); restoreServerPreview(); clearCropFields(); removeField.value = ''; adjust.classList.add('hidden'); fullImage.classList.add('hidden'); clear.classList.add('hidden'); });
        if (remove) { remove.addEventListener('click', function () { if (!window.confirm(REMOVE_CONFIRMATION)) { return; } input.value = ''; emptyPreview(true); clearCropFields(); removeField.value = 'true'; if (serverImage && defaultSource) { serverImage.setAttribute('src', defaultSource); serverImage.setAttribute('alt', "Family Pick'em default logo"); } }); }
        form.addEventListener('submit', function () { if (!cropActive) { clearCropFields(); } if (removeField.value !== 'true') { removeField.value = ''; } });
        window.addEventListener('pagehide', function () { emptyPreview(true); }, { once: true });
    });
})();
