// DEPLOY TEST (change this string every push)
window.__GOLF_BUILD_ID__ = "2026-03-06_inherit_ui_update";
console.log("828ers JS loaded. Build: DATE+TEE INHERIT", window.__GOLF_BUILD_ID__);

const GOLF_AJAX_URL = (typeof GolfMasterAjax !== "undefined") ? GolfMasterAjax.ajaxUrl : "/wp-admin/admin-ajax.php";

/* --------------------------
   Auto-inherit date and tee from row 1 to rows 2, 3, 4
   Fires as soon as the page is ready.
   -------------------------- */
jQuery(function ($) {
    const $rows = $(".entry-row");
    const $row1 = $rows.eq(0);

    $row1.find(".in-date").on("change", function () {
        const val = $(this).val();
        $rows.slice(1).each(function () {
            $(this).find(".in-date").val(val);
        });
    });

    $row1.find(".in-tee").on("change", function () {
        const val = $(this).val();
        $rows.slice(1).each(function () {
            $(this).find(".in-tee").val(val);
        });
    });
});

/* --------------------------
   Delete a historic round
   -------------------------- */
function ajaxDelete(scoreId) {
  if (!confirm("Delete round " + scoreId + "?")) return;

  jQuery
    .post(
      GOLF_AJAX_URL,
      {
        action:   "golf_final_action_delete",
        score_id: scoreId,
        nonce:    GolfMasterAjax.nonce
      },
      function (res) {
        console.log("DELETE response:", res);
        if (res && res.success === true) {
          jQuery("#row-" + scoreId).remove();
          alert("Round " + scoreId + " has been successfully deleted.");
        } else {
          alert(
            (res && res.data && res.data.message) ? res.data.message : "Delete failed."
          );
        }
      },
      "json"
    )
    .fail(function (xhr) {
      console.log("DELETE failed:", xhr.status, xhr.responseText);
      alert("Delete failed (AJAX error). See console.");
    });
}

/* --------------------------
   Update a historic round
   -------------------------- */
function ajaxUpdate(scoreId) {
  const row     = jQuery("#row-" + scoreId);
  const saveBtn = row.find(".btn-save");

  const data = {
    action:   "golf_final_action_update",
    score_id: scoreId,
    date:     row.find(".ed-date").val(),
    tee:      row.find(".ed-tee").val(),
    gross:    row.find(".ed-gross").val(),
    pcc:      row.find(".ed-pcc").val(),
    putts:    row.find(".ed-putts").val(),
    gir:      row.find(".ed-gir").val(),
    excluded: row.find(".ed-excl").is(":checked") ? 1 : 0,
    nonce:    GolfMasterAjax.nonce
  };

  saveBtn.text("SAVING...").prop("disabled", true);

  jQuery
    .post(
      GOLF_AJAX_URL,
      data,
      function (res) {
        console.log("SAVE response:", res);

        if (!res || res.success !== true) {
          alert(
            (res && res.data && res.data.message)
              ? res.data.message
              : "Update failed. See console."
          );
          saveBtn.text("SAVE").prop("disabled", false);
          return;
        }

        let netSpan = row.find(".ed-net .net-val");
        if (netSpan.length === 0) {
            row.find(".ed-net").html('<span class="net-val"></span>');
            netSpan = row.find(".ed-net .net-val");
        }
        netSpan.text(res.data.net_score);
        
        if (parseInt(res.data.is_counting, 10) === 1) {
            netSpan.addClass("count-circle");
        } else {
            netSpan.removeClass("count-circle");
        }

        row.find(".ed-diff").text(res.data.differential);

        // Visually mark row as excluded or restore it
        if (parseInt(res.data.is_excluded, 10) === 1) {
          row.addClass("row-excluded");
        } else {
          row.removeClass("row-excluded");
        }

        saveBtn
          .text("SAVED!")
          .css({ "background-color": "#28a745", color: "#fff" })
          .prop("disabled", false);

        setTimeout(function () {
          saveBtn.text("SAVE").css({ "background-color": "", color: "" });
        }, 2000);
      },
      "json"
    )
    .fail(function (xhr) {
      console.log("SAVE failed:", xhr.status, xhr.responseText);
      alert("Update failed (AJAX error). See console.");
      saveBtn.text("SAVE").prop("disabled", false);
    });
}

/* --------------------------
   Save up to 4 new rounds
   -------------------------- */
function golfSaveAll() {
  let rounds = [];

  jQuery(".entry-row").each(function () {
    const $row      = jQuery(this);
    const player_id = $row.find(".in-player").val();
    const date      = $row.find(".in-date").val();
    const tee       = $row.find(".in-tee").val();
    const gross     = $row.find(".in-gross").val();

    if (player_id && date && tee && gross !== "") {
      rounds.push({
        player_id: player_id,
        date:      date,
        tee:       tee,
        gross:     gross,
        pcc:       $row.find(".in-pcc").val(),
        putts:     $row.find(".in-putts").val(),
        gir:       $row.find(".in-gir").val(),
        // No excluded here — entry form always saves as is_excluded = 0
        // Use the edit grid Excl checkbox to exclude after saving if needed
      });
    }
  });

  if (rounds.length === 0) return alert("Enter at least one round.");

  jQuery
    .post(
      GOLF_AJAX_URL,
      {
        action: "golf_final_action_bulk_save",
        rounds: rounds,
        nonce:  GolfMasterAjax.nonce
      },
      function (res) {
        console.log("BULK SAVE response:", res);

        if (!res || res.success !== true) {
          alert(
            (res && res.data && res.data.message)
              ? res.data.message
              : "Save failed."
          );
          return;
        }

        alert("Successfully saved " + rounds.length + " round(s).");

        const $anyTeeSelect  = jQuery(".golf-edit-box .ed-tee").first();
        const teeOptionsHtml = $anyTeeSelect.length ? $anyTeeSelect.html() : "";
        const $historicBox   = jQuery(".golf-edit-box");
        const $header        = $historicBox.find(".golf-grid-header").first();

        (res.data.rows || []).forEach(function (r) {
          const countClass = parseInt(r.is_counting, 10) === 1 ? "count-circle" : "";

          // New rows from bulk save are never excluded (is_excluded always 0 from entry form)
          const rowHtml = `
            <div class="golf-grid-row edit-row" id="row-${escapeAttr(r.score_id)}">
              <div><strong>${escapeHtml(r.player_name)}</strong></div>
              <input type="date" class="golf-input ed-date" value="${escapeAttr(r.date_played)}">
              <select class="golf-input ed-tee">${teeOptionsHtml}</select>
              <input type="number" class="golf-input ed-gross tc" value="${escapeAttr(r.gross_score)}">
              <input type="number" class="golf-input ed-pcc tc" value="${escapeAttr(r.pcc_adjustment)}">
              <input type="number" class="golf-input ed-putts tc" value="${escapeAttr(r.putts)}">
              <input type="number" class="golf-input ed-gir tc" value="${escapeAttr(r.gir)}">
              <div class="tc"><input type="checkbox" class="golf-input ed-excl" value="1" title="Exclude from handicap"></div>
              <div class="computed tc ed-net">
                  <span class="net-val ${countClass}">${escapeHtml(r.net_score)}</span>
              </div>
              <div class="computed tc ed-diff">${escapeHtml(r.differential)}</div>
              <div class="tc action-btns">
                <button class="golf-btn btn-save" onclick="ajaxUpdate(${escapeAttr(r.score_id)})">SAVE</button>
                <button class="golf-btn btn-del" onclick="ajaxDelete(${escapeAttr(r.score_id)})">DEL</button>
              </div>
            </div>
          `;

          $header.after(rowHtml);
          jQuery("#row-" + r.score_id).find(".ed-tee").val(String(r.tee_id));
        });

        // Clear entry form rows
        jQuery(".entry-row").each(function () {
          const $row = jQuery(this);
          $row.find(".in-player").val("");
          $row.find(".in-gross").val("");
          $row.find(".in-putts").val("");
          $row.find(".in-gir").val("");
          $row.find(".in-pcc").val("0");
          $row.find(".status-cell").text("-");
          // Date and tee intentionally left as-is — ready for the next group of rounds
        });
      },
      "json"
    )
    .fail(function (xhr) {
      console.log("BULK SAVE failed:", xhr.status, xhr.responseText);
      alert("Save failed (AJAX error). See console.");
    });
}

/* --------------------------
   Helpers
   -------------------------- */
function escapeHtml(v) {
  if (v === null || v === undefined) return "";
  return String(v)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttr(v) {
  return escapeHtml(v);
}