const GOLF_AJAX_URL = "/wp-admin/admin-ajax.php";

/* --------------------------
   Delete a historic round
   -------------------------- */
function ajaxDelete(scoreId) {
  if (!confirm("Are you sure you want to delete round " + scoreId + "?")) return;

  jQuery.post(GOLF_AJAX_URL, { action: 'golf_final_action_delete', score_id: scoreId }, function(res) {
    if (res && res.success) {
      jQuery('#row-' + scoreId).remove();
      // Confirmation Alert
      alert("Round " + scoreId + " has been successfully deleted.");
    } else {
      alert("Delete failed.");
    }
  });
}

/* --------------------------
   Update a historic round
   (with button feedback)
   -------------------------- */
function ajaxUpdate(scoreId) {
  const row = jQuery('#row-' + scoreId);
  const saveBtn = row.find('.btn-save');

  const data = {
    action: 'golf_final_action_update',
    score_id: scoreId,
    date: row.find('.ed-date').val(),
    tee: row.find('.ed-tee').val(),
    gross: row.find('.ed-gross').val(),
    pcc: row.find('.ed-pcc').val(),
    putts: row.find('.ed-putts').val(),
    gir: row.find('.ed-gir').val()
  };

  // Set button to "Saving" state
  saveBtn.text('SAVING...').prop('disabled', true);

  jQuery.post(GOLF_AJAX_URL, data, function(res) {
    if (!res || !res.success) {
      alert((res && res.data && res.data.message) ? res.data.message : "Update failed.");
      saveBtn.text('SAVE').prop('disabled', false);
      return;
    }

    // Update computed fields returned by PHP
    row.find('.ed-net').text(res.data.net_score);
    row.find('.ed-diff').text(res.data.differential);

    // Update count dot
    const countCell = row.find('.ed-count');
    countCell.empty();
    if (parseInt(res.data.is_counting, 10) === 1) {
      countCell.append('<span class="count-dot" aria-label="Counting round"></span>');
    }

    // Visual Confirmation: Change button to green "SAVED!"
    saveBtn.text('SAVED!').css('background-color', '#28a745').prop('disabled', false);
    
    // Reset button after 2 seconds
    setTimeout(function() {
      saveBtn.text('SAVE').css('background-color', '');
    }, 2000);
  });
}

/* --------------------------
   Save up to 4 new rounds
   -------------------------- */
function golfSaveAll() {
  let rounds = [];

  jQuery('.entry-row').each(function() {
    const $row = jQuery(this);
    const player_id = $row.find('.in-player').val();
    const date      = $row.find('.in-date').val();
    const tee       = $row.find('.in-tee').val();
    const gross     = $row.find('.in-gross').val();

    if (player_id && date && tee && gross !== "") {
      rounds.push({
        player_id: player_id,
        date: date,
        tee: tee,
        gross: gross,
        pcc: $row.find('.in-pcc').val(),
        putts: $row.find('.in-putts').val(),
        gir: $row.find('.in-gir').val()
      });
    }
  });

  if (rounds.length === 0) return alert("Enter at least one round.");

  jQuery.post(GOLF_AJAX_URL, { action: 'golf_final_action_bulk_save', rounds: rounds }, function(res) {
    if (!res || !res.success) {
      alert((res && res.data && res.data.message) ? res.data.message : "Save failed.");
      return;
    }

    // Confirmation Alert for bulk save
    alert("Successfully saved " + rounds.length + " new round(s).");

    const $anyTeeSelect = jQuery('.golf-edit-box .ed-tee').first();
    const teeOptionsHtml = $anyTeeSelect.length ? $anyTeeSelect.html() : '';
    const $historicBox = jQuery('.golf-edit-box');
    const $header = $historicBox.find('.golf-grid-header').first();

    (res.data.rows || []).forEach(function(r) {
      const countHtml = (parseInt(r.is_counting, 10) === 1)
        ? '<span class="count-dot" aria-label="Counting round"></span>'
        : '';

      const rowHtml = `
        <div class="golf-grid-row" id="row-${escapeAttr(r.score_id)}">
          <div><strong>${escapeHtml(r.player_name)}</strong></div>
          <input type="date" class="golf-input ed-date" value="${escapeAttr(r.date_played)}">
          <select class="golf-input ed-tee">${teeOptionsHtml}</select>
          <input type="number" class="golf-input ed-gross tc" value="${escapeAttr(r.gross_score)}">
          <input type="number" class="golf-input ed-pcc tc" value="${escapeAttr(r.pcc_adjustment)}">
          <input type="number" class="golf-input ed-putts tc" value="${escapeAttr(r.putts)}">
          <input type="number" class="golf-input ed-gir tc" value="${escapeAttr(r.gir)}">
          <div class="computed ed-net">${escapeHtml(r.net_score)}</div>
          <div class="computed ed-diff">${escapeHtml(r.differential)}</div>
          <div class="tc ed-count">${countHtml}</div>
          <div class="tc action-btns">
            <button class="golf-btn btn-save" onclick="ajaxUpdate(${escapeAttr(r.score_id)})">SAVE</button>
            <button class="golf-btn btn-del" onclick="ajaxDelete(${escapeAttr(r.score_id)})">DEL</button>
          </div>
        </div>
      `;

      $header.after(rowHtml);
      jQuery('#row-' + r.score_id).find('.ed-tee').val(String(r.tee_id));
    });

    jQuery('.entry-row').each(function() {
      const $row = jQuery(this);
      $row.find('.in-player').val('');
      $row.find('.in-gross').val('');
      $row.find('.in-putts').val('');
      $row.find('.in-gir').val('');
      $row.find('.in-pcc').val('0');
      $row.find('.status-cell').text('-');
    });
  });
}

/* --------------------------
   Helpers
   -------------------------- */
function escapeHtml(v) {
  if (v === null || v === undefined) return '';
  return String(v)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function escapeAttr(v) {
  return escapeHtml(v);
}