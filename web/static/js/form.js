document.addEventListener('DOMContentLoaded', function () {
  var startTimeInput = document.getElementById('start_time');
  var pattern1Fields = document.getElementById('pattern1-fields');
  var pattern2Fields = document.getElementById('pattern2-fields');
  var pattern3Fields = document.getElementById('pattern3-fields');

  // -------------------------------------------------------
  // Image Picker Dropdown logic
  // -------------------------------------------------------
  document.querySelectorAll('.image-picker').forEach(function (picker) {
    var details = picker.querySelector('details');
    var hidden = picker.querySelector('input[type="hidden"]');
    var preview = picker.querySelector('.selected-preview');
    var label = picker.querySelector('.selected-label');
    var placeholder = picker.querySelector('.placeholder');

    picker.querySelectorAll('.picker-option').forEach(function (btn) {
      btn.addEventListener('click', function () {
        hidden.value = btn.getAttribute('data-value');

        var img = btn.querySelector('img');
        if (img && preview) {
          preview.src = img.src;
          preview.alt = btn.getAttribute('data-label') || '';
          preview.style.display = '';
        }
        if (label) {
          label.textContent = btn.getAttribute('data-label') || '';
          label.style.display = '';
        }
        if (placeholder) {
          placeholder.style.display = 'none';
        }

        picker.querySelectorAll('.picker-option').forEach(function (o) {
          o.classList.remove('selected');
        });
        btn.classList.add('selected');

        details.open = false;

        if (picker.id === 'pattern-picker') {
          onPatternChange();
        }
      });
    });
  });

  // Close dropdowns on outside click
  document.addEventListener('click', function (e) {
    document.querySelectorAll('.image-picker details[open]').forEach(function (d) {
      if (!d.parentElement.contains(e.target)) {
        d.open = false;
      }
    });
  });

  // -------------------------------------------------------
  // Set default datetime to now
  // -------------------------------------------------------
  if (startTimeInput && !startTimeInput.value) {
    var now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    startTimeInput.value = now.toISOString().slice(0, 16);
  }

  // -------------------------------------------------------
  // Pattern change -> switch field sets
  // -------------------------------------------------------
  function onPatternChange() {
    var patternInput = document.querySelector('#pattern-picker input[type="hidden"]');
    if (!patternInput || !patternInput.value) return;

    var p = patternInput.value;

    pattern1Fields.style.display = p === 'パターン1' ? 'block' : 'none';
    pattern2Fields.style.display = p === 'パターン2' ? 'block' : 'none';
    pattern3Fields.style.display = p === 'パターン3' ? 'block' : 'none';
  }

  onPatternChange();
});
