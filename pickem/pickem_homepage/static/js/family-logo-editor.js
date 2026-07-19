/*
 * Progressive enhancement for the family logo setting. The native file input
 * is always submitted normally; this preview never creates or uploads bytes.
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

    ready(function () {
        var form = document.querySelector('[data-family-logo-form]');
        var input = document.getElementById('id_logo');
        var preview = document.querySelector('[data-family-logo-editor]');
        var serverPreview = document.querySelector('[data-family-logo-server-preview]');
        var clear = document.querySelector('[data-family-logo-clear]');
        var remove = document.querySelector('[data-family-logo-remove]');
        var removeField = document.getElementById('id_remove_logo');
        var cropFields = ['crop_x', 'crop_y', 'crop_width', 'crop_height'].map(function (name) {
            return document.getElementById('id_' + name);
        });
        if (!form || !input || !preview || !serverPreview || !clear || !removeField || !window.URL) {
            return;
        }

        var objectUrl = null;
        var serverImage = serverPreview.querySelector('img');
        var savedSource = serverImage && serverImage.getAttribute('src');
        var savedAlt = serverImage && serverImage.getAttribute('alt');
        var defaultSource = serverPreview.getAttribute('data-family-logo-default-src');

        function clearCropFields() {
            cropFields.forEach(function (field) { if (field) { field.value = ''; } });
        }

        function restoreServerPreview() {
            if (serverImage && savedSource) {
                serverImage.setAttribute('src', savedSource);
                serverImage.setAttribute('alt', savedAlt || 'Family logo');
            }
        }

        function clearPreview() {
            while (preview.firstChild) { preview.removeChild(preview.firstChild); }
            preview.classList.add('hidden');
            preview.classList.remove('flex');
            serverPreview.classList.remove('hidden');
            clear.classList.add('hidden');
            if (objectUrl) { window.URL.revokeObjectURL(objectUrl); objectUrl = null; }
        }

        function showPreview(file) {
            clearPreview();
            objectUrl = window.URL.createObjectURL(file);
            var image = document.createElement('img');
            image.src = objectUrl;
            image.alt = 'Selected family logo preview';
            image.className = 'max-h-full max-w-full object-contain';
            preview.appendChild(image);
            preview.classList.remove('hidden');
            preview.classList.add('flex');
            serverPreview.classList.add('hidden');
            clear.classList.remove('hidden');
            clearCropFields();
            removeField.value = '';
        }

        input.addEventListener('change', function () {
            var file = input.files && input.files[0];
            if (!file) {
                clearPreview();
                restoreServerPreview();
                clearCropFields();
                removeField.value = '';
                return;
            }
            showPreview(file);
        });

        clear.addEventListener('click', function () {
            input.value = '';
            clearPreview();
            restoreServerPreview();
            clearCropFields();
            removeField.value = '';
        });

        if (remove) {
            remove.addEventListener('click', function () {
                if (!window.confirm(REMOVE_CONFIRMATION)) { return; }
                input.value = '';
                clearPreview();
                clearCropFields();
                removeField.value = 'true';
                if (serverImage && defaultSource) {
                    serverImage.setAttribute('src', defaultSource);
                    serverImage.setAttribute('alt', "Family Pick'em default logo");
                }
            });
        }

        form.addEventListener('submit', function () {
            if (removeField.value !== 'true') { removeField.value = ''; }
            clearCropFields();
        });
        window.addEventListener('pagehide', clearPreview, { once: true });
    });
})();
