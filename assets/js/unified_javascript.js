// DEPLOY TEST (change this string every push)
window.__GOLF_BUILD_ID__ = "2026-03-23_inherit_ui_duplicate_warning";
console.log("828ers JS loaded. Build: DATE+TEE INHERIT + DUPLICATE WARNING", window.__GOLF_BUILD_ID__);

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
  let duplicateWarning = false;
  let warningMessage = "";

  // 1. Build a list of existing player+date combos from the Edit Grid below
  let existingRounds = [];
  jQuery(".golf-edit-box .edit-row").each(function () {
    let pName = jQuery(this).find("div:first-child strong").text().trim();
    let pDate = jQuery(this).find(".ed-date").val();
    if (pName && pDate) {
      existingRounds.push(pName + "|" + pDate);
    }
  });

  // 2. Track what is currently being submitted in the top form
  let submittedRounds = new Set();

  jQuery(".entry-row").each(function () {
    const $row        = jQuery(this);
    const player_id   = $row.find(".in-player").val();
    const player_name = $row.find(".in-player option:selected").text().trim();
    const date        = $row.find(".in-date").val();
    const course_id   = $row.find(".in-course").val();
    const tee_text    = $row.find(".in-tee option:selected").text().trim();
    const tee         = $row.find(".in-tee").val();
    const gross       = $row.find(".in-gross").val();

    if (player_id && date && tee && gross !== "") {
      let comboKey = player_name + "|" + date;

      // Check if this player+date is already in the current batch being submitted
      if (submittedRounds.has(comboKey)) {
          duplicateWarning = true;
          warningMessage = "You have entered multiple rounds for " + player_name + " on " + date + " in the top form.\n\nAre you sure you want to save multiple rounds for the same player on the same day?";
      }
      submittedRounds.add(comboKey);

      // Check if this player+date is already in the historic grid below
      if (existingRounds.includes(comboKey) && !duplicateWarning) {
          duplicateWarning = true;
          warningMessage = player_name + " already has a saved round on " + date + " in the historic grid below.\n\nAre you sure you want to add another round for them on this same day?";
      }

      rounds.push({
        player_id: player_id,
        date:      date,
        course_id: course_id,
        tee_text:  tee_text,
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

  // 3. Trigger the warning if needed
  if (duplicateWarning) {
      if (!confirm("⚠️ WARNING:\n\n" + warningMessage)) {
          return; // User clicked Cancel, abort the save entirely
      }
  }

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

        // Reload the page so the historic grid, counting dots, and totals all refresh from the database.
        window.setTimeout(function () {
          window.location.reload();
        }, 500);
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