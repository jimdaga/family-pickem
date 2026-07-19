/*
 * Progressive enhancement for the family settings form.  This controller
 * deliberately never creates upload bytes: the native file input is submitted
 * normally and Pillow remains the authority for image safety and output.
 */
(function () {
    'use strict';

    var REMOVE_CONFIRMATION = 'Remove family logo? Your family will use the default logo after you save settings.';

    function ready(callback) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', callback);
        } else {
            callback();
        }
    }

    // EXIF orientation is intentionally conservative.  Pillow transposes the
    // server source, and a browser preview cannot prove matching coordinates on
    // every browser.  Rotated sources therefore use the secure server-center
    // fallback instead of posting possibly wrong crop coordinates.
    function readJpegOrientation(file) {
        if (!file || file.type !== 'image/jpeg' || !window.FileReader) {
            return Promise.resolve(1);
        }
        return new Promise(function (resolve) {
            var reader = new FileReader();
            reader.onerror = function () { resolve(null); };
            reader.onload = function () {
                var view = new DataView(reader.result);
                if (view.getUint16(0, false) !== 0xFFD8) { resolve(1); return; }
                var offset = 2;
                while (offset + 4 < view.byteLength) {
                    var marker = view.getUint16(offset, false);
                    offset += 2;
                    if (marker === 0xFFE1) {
                        var length = view.getUint16(offset, false);
                        var exif = offset + 2;
                        if (exif + 8 > view.byteLength || view.getUint32(exif, false) !== 0x45786966) { resolve(1); return; }
                        var tiff = exif + 6;
                        var little = view.getUint16(tiff, false) === 0x4949;
                        var firstIfd = tiff + view.getUint32(tiff + 4, little);
                        var count = view.getUint16(firstIfd, little);
                        for (var index = 0; index < count; index += 1) {
                            var entry = firstIfd + 2 + (index * 12);
                            if (entry + 12 <= view.byteLength && view.getUint16(entry, little) === 0x0112) {
                                resolve(view.getUint16(entry + 8, little));
                                return;
                            }
                        }
                        resolve(1); return;
                    }
                    if ((marker & 0xFF00) !== 0xFF00) { break; }
                    offset += view.getUint16(offset, false);
                }
                resolve(1);
            };
            reader.readAsArrayBuffer(file.slice(0, 65536));
        });
    }

    ready(function () {
        var form = document.querySelector('[data-family-logo-form]');
        var input = document.getElementById('id_logo');
        var editorHost = document.querySelector('[data-family-logo-editor]');
        var serverPreview = document.querySelector('[data-family-logo-server-preview]');
        var actions = document.querySelector('[data-family-logo-actions]');
        var reset = document.querySelector('[data-family-logo-reset]');
        var clear = document.querySelector('[data-family-logo-clear]');
        var remove = document.querySelector('[data-family-logo-remove]');
        var fields = ['crop_x', 'crop_y', 'crop_width', 'crop_height'].map(function (name) {
            return document.getElementById('id_' + name);
        });
        var removeField = document.getElementById('id_remove_logo');
        if (!form || !input || !editorHost || !serverPreview || !actions || !reset || !clear || !removeField || !window.URL || !window.customElements || !window.customElements.get('cropper-canvas')) {
            return;
        }

        var state = 'saved';
        var objectUrl = null;
        var cropper = null;
        var cropperImage = null;
        var cropperSelection = null;
        var orientationUnsafe = false;
        var serverImage = serverPreview.querySelector('img');
        var savedSource = serverImage && serverImage.getAttribute('src');
        var savedAlt = serverImage && serverImage.getAttribute('alt');
        var defaultSource = serverPreview.getAttribute('data-family-logo-default-src');

        function restoreServerPreview() {
            if (serverImage && savedSource) {
                serverImage.setAttribute('src', savedSource);
                serverImage.setAttribute('alt', savedAlt || 'Family logo');
            }
        }

        function clearCropFields() {
            fields.forEach(function (field) { if (field) { field.value = ''; } });
        }

        function removeEditor() {
            // Cropper.js v2 lifecycle: remove its component subtree ourselves.
            // Do not use the v1-style destroy API.
            if (cropperImage) { cropperImage.removeAttribute('src'); }
            while (editorHost.firstChild) { editorHost.removeChild(editorHost.firstChild); }
            cropper = null;
            cropperImage = null;
            cropperSelection = null;
            if (objectUrl) { window.URL.revokeObjectURL(objectUrl); objectUrl = null; }
            editorHost.classList.add('hidden');
            serverPreview.classList.remove('hidden');
            actions.classList.add('hidden');
            clear.classList.add('hidden');
        }

        function selectionToSourcePixels() {
            if (orientationUnsafe || !cropperImage || !cropperSelection) {
                clearCropFields();
                return;
            }
            var selectionRect = cropperSelection.getBoundingClientRect();
            var imageRect = cropperImage.getBoundingClientRect();
            var naturalWidth = cropperImage.$image && cropperImage.$image.naturalWidth;
            var naturalHeight = cropperImage.$image && cropperImage.$image.naturalHeight;
            if (!naturalWidth || !naturalHeight || !imageRect.width || !imageRect.height) {
                clearCropFields();
                return;
            }
            var x = Math.round((selectionRect.left - imageRect.left) * naturalWidth / imageRect.width);
            var y = Math.round((selectionRect.top - imageRect.top) * naturalHeight / imageRect.height);
            var side = Math.round(Math.min(selectionRect.width * naturalWidth / imageRect.width, selectionRect.height * naturalHeight / imageRect.height));
            x = Math.max(0, x);
            y = Math.max(0, y);
            side = Math.min(side, naturalWidth - x, naturalHeight - y);
            if (!Number.isSafeInteger(x) || !Number.isSafeInteger(y) || !Number.isSafeInteger(side) || side <= 0) {
                clearCropFields();
                return;
            }
            fields[0].value = String(x);
            fields[1].value = String(y);
            fields[2].value = String(side);
            fields[3].value = String(side);
        }

        function resetCrop() {
            if (!cropperImage || !cropperSelection) { return; }
            cropperImage.$resetTransform();
            cropperSelection.$reset();
            window.requestAnimationFrame(selectionToSourcePixels);
        }

        function renderSelection(file, url, orientation) {
            removeEditor();
            restoreServerPreview();
            objectUrl = url;
            orientationUnsafe = orientation !== 1;
            var canvas = document.createElement('cropper-canvas');
            canvas.setAttribute('background', '');
            canvas.style.width = '100%';
            canvas.style.height = '100%';
            var cropperImageElement = document.createElement('cropper-image');
            cropperImageElement.setAttribute('translatable', '');
            cropperImageElement.setAttribute('scalable', '');
            cropperImageElement.setAttribute('src', objectUrl);
            cropperImageElement.setAttribute('alt', 'Selected family logo preview');
            var shade = document.createElement('cropper-shade');
            var selection = document.createElement('cropper-selection');
            selection.setAttribute('initial-coverage', '0.7');
            selection.setAttribute('aspect-ratio', '1');
            selection.setAttribute('initial-aspect-ratio', '1');
            selection.setAttribute('movable', '');
            selection.setAttribute('resizable', '');
            var grid = document.createElement('cropper-grid');
            grid.setAttribute('role', 'grid');
            grid.setAttribute('bordered', '');
            grid.setAttribute('covered', '');
            var crosshair = document.createElement('cropper-crosshair');
            crosshair.setAttribute('centered', '');
            var moveHandle = document.createElement('cropper-handle');
            moveHandle.setAttribute('action', 'move');
            moveHandle.setAttribute('theme-color', 'rgba(255, 255, 255, 0.35)');
            selection.appendChild(grid);
            selection.appendChild(crosshair);
            selection.appendChild(moveHandle);
            ['n', 'e', 's', 'w', 'ne', 'nw', 'se', 'sw'].forEach(function (direction) {
                var resizeHandle = document.createElement('cropper-handle');
                resizeHandle.setAttribute('action', direction + '-resize');
                selection.appendChild(resizeHandle);
            });
            canvas.appendChild(cropperImageElement);
            canvas.appendChild(shade);
            canvas.appendChild(selection);
            editorHost.appendChild(canvas);
            editorHost.classList.remove('hidden');
            serverPreview.classList.add('hidden');
            actions.classList.remove('hidden');
            clear.classList.remove('hidden');
            removeField.value = '';
            state = 'selected-file';
            cropper = canvas;
            cropperImage = cropperImageElement;
            cropperSelection = selection;
            if (!cropperImage || !cropperSelection) {
                removeEditor();
                return;
            }
            cropperSelection.addEventListener('change', function () {
                window.requestAnimationFrame(selectionToSourcePixels);
            });
            cropperImage.$ready(function () {
                cropperImage.$center('cover');
                window.requestAnimationFrame(selectionToSourcePixels);
            }).catch(function () {
                clearCropFields();
            });
        }

        input.addEventListener('change', function () {
            var file = input.files && input.files[0];
            if (!file) {
                removeEditor();
                clearCropFields();
                removeField.value = '';
                state = 'saved';
                return;
            }
            readJpegOrientation(file).then(function (orientation) {
                if (!input.files || input.files[0] !== file) { return; }
                renderSelection(file, window.URL.createObjectURL(file), orientation);
            });
        });

        reset.addEventListener('click', resetCrop);
        clear.addEventListener('click', function () {
            input.value = '';
            removeEditor();
            clearCropFields();
            removeField.value = '';
            state = 'saved';
        });
        if (remove) {
            remove.addEventListener('click', function () {
                if (!window.confirm(REMOVE_CONFIRMATION)) { return; }
                input.value = '';
                removeEditor();
                clearCropFields();
                removeField.value = 'true';
                if (serverImage && defaultSource) {
                    serverImage.setAttribute('src', defaultSource);
                    serverImage.setAttribute('alt', "Family Pick'em default logo");
                }
                state = 'remove-staged';
            });
        }
        form.addEventListener('submit', function () {
            if (state === 'selected-file') { selectionToSourcePixels(); }
            if (state !== 'remove-staged') { removeField.value = ''; }
        });
        window.addEventListener('pagehide', removeEditor, { once: true });
    });
})();
