// DEPLOY TEST (change this string every push)
window.__GOLF_BUILD_ID__ = "2026-01-31_1842_b";
console.log("828ers JS loaded. Build:", window.__GOLF_BUILD_ID__);

// NOTE: Better long-term is to inject this via wp_localize_script(admin_url('admin-ajax.php'))
const GOLF_AJAX_URL = "/wp-admin/admin-ajax.php";

/* --------------------------
   Delete a historic round
   -------------------------- */
function ajaxDelete(scoreId) {
  if (!confirm("Delete round " + scoreId + "?")) return;

  jQuery
    .post(
      GOLF_AJAX_URL,
      { action: "golf_final_action_delete", score_id: scoreId },
      function (res) {
        console.log("DELETE response:", res);

        if (res && res.success === true) {
          jQuery("#row-" + scoreId).remove();
          alert("Round " + scoreId + " has been successfully deleted.");
        } else {
          alert(
            (res && res.data && res.data.message)
              ? res.data.message
              : "Delete failed."
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
  const row = jQuery("#row-" + scoreId);
  const saveBtn = row.find(".btn-save");

  const data = {
    action: "golf_final_action_update",
    score_id: scoreId,
    date: row.find(".ed-date").val(),
    tee: row.find(".ed-tee").val(),
    gross: row.find(".ed-gross").val(),
    pcc: row.find(".ed-pcc").val(),
    putts: row.find(".ed-putts").val(),
    gir: row.find(".ed-gir").val(),
  };

  // Immediate feedback
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

        // Update computed fields returned by PHP
        row.find(".ed-net").text(res.data.net_score);
        row.find(".ed-diff").text(res.data.differential);

        // Update count dot
        const countCell = row.find(".ed-count");
        countCell.empty();
        if (parseInt(res.data.is_counting, 10) === 1) {
          countCell.append(
            '<span class="count-dot" aria-label="Counting round"></span>'
          );
        }

        // Visual confirmation: Turn button green and show "SAVED!"
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
    const $row = jQuery(this);
    const player_id = $row.find(".in-player").val();
    const date = $row.find(".in-date").val();
    const tee = $row.find(".in-tee").val();
    const gross = $row.find(".in-gross").val();

    if (player_id && date && tee && gross !== "") {
      rounds.push({
        player_id: player_id,
        date: date,
        tee: tee,
        gross: gross,
        pcc: $row.find(".in-pcc").val(),
        putts: $row.find(".in-putts").val(),
        gir: $row.find(".in-gir").val(),
      });
    }
  });

  if (rounds.length === 0) return alert("Enter at least one round.");

  jQuery
    .post(
      GOLF_AJAX_URL,
      { action: "golf_final_action_bulk_save", rounds: rounds },
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

        const $anyTeeSelect = jQuery(".golf-edit-box .ed-tee").first();
        const teeOptionsHtml = $anyTeeSelect.length ? $anyTeeSelect.html() : "";
        const $historicBox = jQuery(".golf-edit-box");
        const $header = $historicBox.find(".golf-grid-header").first();

        (res.data.rows || []).forEach(function (r) {
          const countHtml =
            parseInt(r.is_counting, 10) === 1
              ? '<span class="count-dot" aria-label="Counting round"></span>'
              : "";

          // FIX: add "edit-row" so inserted rows match existing grid styling
          const rowHtml = `
            <div class="golf-grid-row edit-row" id="row-${escapeAttr(r.score_id)}">
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

          // Belt-and-braces: force the class even if something strips it
          jQuery("#row-" + r.score_id).addClass("edit-row");

          jQuery("#row-" + r.score_id).find(".ed-tee").val(String(r.tee_id));
        });

        jQuery(".entry-row").each(function () {
          const $row = jQuery(this);
          $row.find(".in-player").val("");
          $row.find(".in-gross").val("");
          $row.find(".in-putts").val("");
          $row.find(".in-gir").val("");
          $row.find(".in-pcc").val("0");
          $row.find(".status-cell").text("-");
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
