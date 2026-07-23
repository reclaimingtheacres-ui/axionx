(function(){
  'use strict';

  var AX_COMPRESS_MAX_DIM = 2048;
  var AX_COMPRESS_QUALITY = 0.85;

  function _isImage(file) {
    return file && file.type && file.type.startsWith('image/');
  }

  function _compressOne(file) {
    return new Promise(function(resolve) {
      if (!_isImage(file)) { resolve(file); return; }

      if (file.type === 'image/svg+xml') { resolve(file); return; }

      var url = URL.createObjectURL(file);
      var img = new Image();
      img.onload = function() {
        var w = img.naturalWidth, h = img.naturalHeight;
        if (w > AX_COMPRESS_MAX_DIM || h > AX_COMPRESS_MAX_DIM) {
          var ratio = Math.min(AX_COMPRESS_MAX_DIM / w, AX_COMPRESS_MAX_DIM / h);
          w = Math.round(w * ratio);
          h = Math.round(h * ratio);
        }
        var canvas = document.createElement('canvas');
        canvas.width = w; canvas.height = h;
        var ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, w, h);
        canvas.toBlob(function(blob) {
          URL.revokeObjectURL(url);
          if (blob && blob.size < file.size) {
            var fname = (file.name || 'photo.jpg').replace(/\.(hei[cf]|png|webp|bmp|tiff?)$/i, '.jpg');
            if (!/\.jpe?g$/i.test(fname)) fname += '.jpg';
            resolve(new File([blob], fname, { type: 'image/jpeg', lastModified: Date.now() }));
          } else {
            resolve(file);
          }
        }, 'image/jpeg', AX_COMPRESS_QUALITY);
      };
      img.onerror = function() {
        URL.revokeObjectURL(url);
        resolve(file);
      };
      img.src = url;
    });
  }

  window.axCompressImage = function(file) {
    return _compressOne(file);
  };

  window.axCompressFiles = function(files) {
    var arr = [];
    for (var i = 0; i < files.length; i++) arr.push(files[i]);
    return Promise.all(arr.map(_compressOne));
  };

  window.axCompressFormData = function(fd, fieldNames) {
    if (!fieldNames) fieldNames = null;
    var entries = [];
    var fileEntries = [];
    for (var pair of fd.entries()) {
      if (pair[1] instanceof File && _isImage(pair[1]) && (!fieldNames || fieldNames.indexOf(pair[0]) >= 0)) {
        fileEntries.push({ key: pair[0], file: pair[1] });
      } else {
        entries.push({ key: pair[0], value: pair[1] });
      }
    }
    if (fileEntries.length === 0) return Promise.resolve(fd);

    return Promise.all(fileEntries.map(function(e) { return _compressOne(e.file); }))
      .then(function(compressed) {
        var newFd = new FormData();
        entries.forEach(function(e) { newFd.append(e.key, e.value); });
        compressed.forEach(function(f, i) { newFd.append(fileEntries[i].key, f); });
        return newFd;
      });
  };

  window._axShowCompressMsg = function(container) {
    if (!container) container = document.body;
    var el = document.createElement('div');
    el.id = 'ax-compress-msg';
    el.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);z-index:99999;background:rgba(0,0,0,.75);color:#fff;padding:14px 28px;border-radius:12px;font-size:.9rem;font-weight:600;display:flex;align-items:center;gap:10px;pointer-events:none;';
    el.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" stroke="#fff" fill="none" stroke-width="2"><circle cx="12" cy="12" r="10" stroke-dasharray="31.4" stroke-dashoffset="10"><animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur=".8s" repeatCount="indefinite"/></circle></svg> Optimising photo\u2026';
    document.body.appendChild(el);
    return el;
  };

  window._axHideCompressMsg = function() {
    var el = document.getElementById('ax-compress-msg');
    if (el) el.remove();
  };

  window.axInterceptFormImages = function(form, fileFieldNames) {
    if (!form) return;
    form.addEventListener('submit', function(e) {
      if (e.defaultPrevented) return;
      if (form.getAttribute('data-ax-compressing')) return;
      var fileInputs = form.querySelectorAll('input[type="file"]');
      var toCompress = [];
      fileInputs.forEach(function(inp) {
        if (!fileFieldNames || fileFieldNames.indexOf(inp.name) >= 0) {
          for (var i = 0; i < inp.files.length; i++) {
            if (_isImage(inp.files[i])) { toCompress.push(inp); break; }
          }
        }
      });
      if (!toCompress.length) return;

      e.preventDefault();
      form.setAttribute('data-ax-compressing', '1');
      _axShowCompressMsg();

      var tasks = toCompress.map(function(inp) {
        var files = [];
        for (var i = 0; i < inp.files.length; i++) files.push(inp.files[i]);
        return Promise.all(files.map(_compressOne)).then(function(compressed) {
          var dt = new DataTransfer();
          compressed.forEach(function(f) { dt.items.add(f); });
          inp.files = dt.files;
        });
      });

      Promise.all(tasks).then(function() {
        _axHideCompressMsg();
        form.removeAttribute('data-ax-compressing');
        form.submit();
      }).catch(function() {
        _axHideCompressMsg();
        form.removeAttribute('data-ax-compressing');
        form.submit();
      });
    });
  };

})();
