/* ======================================================
   GOLF SYSTEM — UNIFIED CSS (UPDATED)
   - Winner colours + TIE handling
   - Better pivot table polish
   - Pagination spacing fix (Prev/Next)
   - 7-column entry grid (PCC removed)
   ====================================================== */

/* Global container settings */
.golf-history-container,
.golf-management-root,
.golf-dashboard-wrapper{
  margin-top:30px;
  scroll-margin-top:80px;
  font-family: inherit !important;
}

.tc{ text-align:center; }
.tr{ text-align:right; }

/* ======================================================
   DASHBOARD (HOME) — cards + sections
   ====================================================== */
.golf-dashboard-wrapper{ scroll-margin-top:50px; }

.stats-filter-bar{
  background:#f9f9f9;
  padding:15px;
  border-radius:5px;
  margin-bottom:20px;
  text-align:center;
  border:1px solid #ddd;
}

.golf-stats-grid{
  display:grid;
  grid-template-columns:repeat(4, 1fr);
  gap:15px;
  align-items:stretch;
}

.golf-card{
  background:#fff;
  border:1px solid #ddd;
  border-radius:4px;
  display:flex;
  flex-direction:column;
  height:100%;
}

.card-header{
  background:#333;
  color:#fff;
  padding:10px;
  display:flex;
  justify-content:space-between;
  font-weight:bold;
}

.p-idx{ color:#f39c12; }

.sect-title{
  font-size:10px;
  font-weight:bold;
  color:#888;
  margin-bottom:8px;
  text-transform:uppercase;
}

.sect-hcap{
  padding:12px;
  background:#f9f9f9;
  border-bottom:1px solid #eee;
  min-height:125px;
}

.sect-averages{
  padding:12px;
  background:#fdfdfd;
  border-bottom:1px solid #eee;
  min-height:55px;
}
.sect-averages span{ color:#666; font-size:13px; }
.sect-averages strong{ color:#333; }

.sect-stats{
  padding:12px;
  border-bottom:1px solid #eee;
  min-height:250px;
  flex-grow:1;
}

.sect-recs{
  padding:12px;
  min-height:105px;
}

.stats-table{
  width:100%;
  border-collapse:collapse;
  font-size:13px;
  line-height:1.2;
}
.stats-table td{ padding:4px 0; border-bottom:1px solid #f5f5f5; }
.txt-pct{ color:#999; font-size:10px; padding-right:8px; }
.rec-sub{ color:#888; font-size:11px; display:block; margin-top:2px; }

/* If Ultimate Member login appears anywhere */
.um.um-login,
.um.um-login *{ color:#ffffff; }

/* ======================================================
   HISTORY TABLE (HOME + HISTORY)
   ====================================================== */
.history-scroll{
  overflow-x:auto;
  border:1px solid #ddd;
  border-radius:4px;
  background:#fff;
}
.history-table{
  width:100%;
  border-collapse:collapse;
  font-size:13px;
}
.history-table th{
  background:#f4f4f4;
  color:#333;
  text-align:left;
  padding:12px 10px;
  border-bottom:2px solid #ddd;
  white-space:nowrap;
}
.history-table td{
  padding:10px 8px;
  border-bottom:1px solid #eee;
  white-space:nowrap;
}
.history-table tr:nth-child(even){ background-color:#fcfcfc; }

/* Filter bar */
.history-filter-bar{
  background:#f1f1f1;
  padding:15px;
  border-radius:8px;
  margin-bottom:25px;
  border:1px solid #ddd;
  display:flex;
  align-items:center;
  gap:10px;
}
.history-filter-bar label{
  font-size:14px;
  font-weight:bold;
  color:#333;
}

/* Tee badges + counting dot */
.tee-badge{
  padding:4px 12px;
  border-radius:15px;
  font-size:11px;
  font-weight:bold;
  text-transform:uppercase;
  display:inline-block;
}
.tee-white{ background:#fff; color:#333; border:1px solid #ccc; }
.tee-yellow{ background:#ffeb3b; color:#333; }
.tee-black{ background:#000; color:#fff; }

.count-dot,
.counting-dot{
  height:10px;
  width:10px;
  background-color:#137a3d;
  border-radius:50%;
  display:inline-block;
  margin:0 auto;
}

/* ======================================================
   PAGINATION — FIX "Prev3Next"
   Works for your .history-pagination and many table plugins
   ====================================================== */
.history-pagination{
  margin-top:25px;
  text-align:center;
  display:flex;
  justify-content:center;
  align-items:center;
  gap:8px;
  flex-wrap:wrap;
}

.history-pagination .page-numbers{
  padding:8px 14px;
  border:1px solid #ddd;
  border-radius:6px;
  margin:0;
  background:#fff;
  color:#333;
  display:inline-flex;
  align-items:center;
  justify-content:center;
  text-decoration:none;
  line-height:1;
  min-width:42px;
}
.history-pagination .page-numbers:hover{
  background:#f3f4f6;
}
.history-pagination .current{
  background:#0073aa;
  color:#fff;
  border-color:#0073aa;
}

.history-pagination a + a,
.history-pagination a + span,
.history-pagination span + a{
  margin-left:8px !important;
}

.dataTables_paginate,
.wpDataTablesWrapper .dataTables_paginate{
  display:flex;
  justify-content:flex-end;
  align-items:center;
  gap:8px;
  padding:10px 0;
}
.dataTables_paginate a,
.wpDataTablesWrapper .dataTables_paginate a,
.dataTables_paginate span,
.wpDataTablesWrapper .dataTables_paginate span{
  margin:0 !important;
}
.dataTables_paginate a,
.wpDataTablesWrapper .dataTables_paginate a{
  padding:6px 10px;
  border:1px solid #d1d5db;
  border-radius:6px;
  background:#fff;
  text-decoration:none;
  line-height:1;
}
.dataTables_paginate .current,
.wpDataTablesWrapper .dataTables_paginate .current{
  padding:6px 10px;
  border-radius:6px;
  background:#111827;
  color:#fff !important;
  border:1px solid #111827;
}

/* ======================================================
   INPUTS / BUTTONS / BOXES (SCORES PAGE)
   ====================================================== */
.golf-entry-box,
.golf-edit-box{
  background:#fff;
  border:1px solid #ddd;
  border-radius:4px;
  margin-bottom:40px;
}

.golf-input{
  width:100%;
  padding:5px;
  border:1px solid #ccc;
  border-radius:3px;
  font-size:13px;
  background:#fff;
}

.golf-btn{
  border:none;
  padding:8px;
  border-radius:3px;
  cursor:pointer;
  font-size:10px;
  font-weight:bold;
  text-transform:uppercase;
  transition:opacity .2s;
  white-space:nowrap;
}
.golf-btn:hover{ opacity:.8; }
.btn-save{ background:#0073aa; color:#fff; }
.btn-del{ background:#d63638; color:#fff; }

.golf-entry-box .entry-footer{
  padding:15px;
  text-align:right;
  background:#f9f9f9;
}
.golf-entry-box .entry-footer .golf-btn.btn-save{
  min-height:34px;
  padding:0 14px !important;
  line-height:1 !important;
  display:inline-flex;
  align-items:center;
  justify-content:center;
}

/* ======================================================
   GRIDS (SCOPED) — 7-column entry, 11-column edit
   ====================================================== */
.golf-grid-header{
  background:#333;
  color:#fff;
  font-weight:bold;
  font-size:11px;
  text-transform:uppercase;
}

/* Entry grid: 7 columns (PCC removed) */
.golf-entry-box .entry-header,
.golf-entry-box .entry-row{
  display:grid;
  grid-template-columns:
    1.3fr
    1.1fr
    0.9fr
    0.7fr
    0.6fr
    0.6fr
    0.6fr;
  gap:10px;
  padding:10px;
  align-items:center;
  border-bottom:1px solid #eee;
}

/* Edit grid: 11 columns */
.golf-edit-box .edit-header,
.golf-edit-box .edit-row{
  display:grid;
  grid-template-columns:
    1.3fr
    1.1fr
    0.9fr
    0.7fr
    0.5fr
    0.6fr
    0.6fr
    0.7fr
    0.7fr
    0.6fr
    1.0fr;
  gap:10px;
  padding:10px;
  align-items:center;
  border-bottom:1px solid #eee;
}

@media (min-width: 768px){
  .golf-entry-box .entry-row .lbl{ display:none !important; }
}

/* ======================================================
   MOBILE OVERRIDES
   ====================================================== */
@media (max-width: 767px){

  .golf-stats-grid{
    display:flex !important;
    flex-direction:column !important;
    grid-template-columns:none !important;
    gap:15px !important;
  }

  .sect-averages{
    padding:10px 12px;
    min-height:auto;
  }
  .sect-averages div{
    flex-direction:column;
    gap:5px;
  }

  .history-table th:nth-child(5), .history-table td:nth-child(5),
  .history-table th:nth-child(6), .history-table td:nth-child(6),
  .history-table th:nth-child(7), .history-table td:nth-child(7),
  .history-table th:nth-child(8), .history-table td:nth-child(8){
    display:none !important;
  }

  .history-table .tee-badge{
    font-size:0 !important;
    width:18px; height:18px; line-height:18px;
    padding:0 !important;
    border-radius:50%;
    display:inline-block;
    text-align:center;
  }
  .history-table .tee-badge:after{ font-size:10px !important; font-weight:bold; }
  .history-table .tee-black:after{  content:'B'; color:#fff; }
  .history-table .tee-yellow:after{ content:'Y'; color:#000; }
  .history-table .tee-white:after{  content:'W'; color:#000; }

  .history-table th,
  .history-table td{
    padding:6px 3px !important;
    font-size:11px !important;
  }

  .history-pagination .page-numbers{ display:none !important; }
  .history-pagination .prev,
  .history-pagination .current,
  .history-pagination .next{ display:inline-flex !important; }

  .golf-management-root.golf-entry-box{ margin-top:8px !important; }

  .golf-entry-box .entry-header{ display:none !important; }
  .golf-entry-box .entry-row .in-pcc,
  .golf-entry-box .entry-row .status-cell{ display:none !important; }

  .golf-entry-box .entry-row{
    display:grid !important;
    grid-template-columns:1fr 1fr !important;
    grid-template-areas:
      "player date"
      "tee    gross"
      "putts  gir";
    gap:6px 6px !important;
    padding:8px !important;
    margin:6px 0 !important;
    border:1px solid #e4e4e4 !important;
    border-radius:10px !important;
    background:#fff !important;
    align-items:stretch !important;
  }

  .golf-entry-box .entry-row .in-player{   grid-area: player; }
  .golf-entry-box .entry-row .in-date{     grid-area: date; }
  .golf-entry-box .entry-row .field-tee{   grid-area: tee; }
  .golf-entry-box .entry-row .field-gross{ grid-area: gross; }
  .golf-entry-box .entry-row .field-putts{ grid-area: putts; }
  .golf-entry-box .entry-row .field-gir{   grid-area: gir; }

  .golf-entry-box .entry-row .field{
    width:100%;
    margin:0 !important;
    padding:0 !important;
    display:flex;
    flex-direction:column;
    justify-content:center;
  }

  .golf-entry-box .entry-row .lbl{
    display:block;
    font-size:6px !important;
    line-height:1 !important;
    font-weight:600 !important;
    text-transform:uppercase !important;
    color:#777 !important;
    margin:0 0 1px 2px !important;
    padding:0 !important;
  }

  .golf-entry-box .entry-row select,
  .golf-entry-box .entry-row input{
    width:100% !important;
    min-height:34px !important;
    padding:4px 6px !important;
    font-size:13px !important;
    border-radius:6px !important;
    box-sizing:border-box !important;
  }

  .golf-entry-box .entry-footer{ padding:6px !important; }
  .golf-entry-box .entry-footer .golf-btn.btn-save{
    width:100% !important;
    min-height:40px !important;
    font-size:11px !important;
  }
}

/* ======================================================
   ROUNDS PIVOT TABLE (grp5) — UPDATED WINNER STYLING
   ====================================================== */

body .grp5,
body .grp5 *{
  font-family: inherit !important;
}

body .grp5 table{
  width:100%;
  border-collapse: collapse !important;
}

body .grp5 table th,
body .grp5 table td{
  border:1px solid #efefef !important;
}

body .grp5 table th.col-date,
body .grp5 table td.col-date,
body .grp5 table thead th:first-child,
body .grp5 table tbody td:first-child{
  white-space:nowrap !important;
}

body .grp5 table thead tr:first-child th{
  text-align:center !important;
  vertical-align:middle !important;
}

body .grp5 table thead tr:first-child th:first-child,
body .grp5 table thead tr:first-child th:nth-child(2){
  text-align:left !important;
}

body .grp5 table thead th{
  background:#333 !important;
  color:#fff !important;
  font-size:11px;
  text-transform:uppercase;
  letter-spacing:1px;
  border-bottom:2px solid #222 !important;
}
body .grp5 table thead tr:nth-child(2) th{
  background:#444 !important;
  font-size:10px;
}

body .grp5 table tbody tr:nth-child(even) td{ background:#fafafa !important; }
body .grp5 table tbody tr:hover td{ background:#f1f7ff !important; }

body .grp5 table tbody td:nth-child(6),
body .grp5 table tbody td:nth-child(9),
body .grp5 table tbody td:nth-child(12),
body .grp5 table tbody td:last-child{
  border-left:2px solid #c8c8c8 !important;
}

body .grp5 table thead tr:nth-child(2) th:nth-child(6),
body .grp5 table thead tr:nth-child(2) th:nth-child(9),
body .grp5 table thead tr:nth-child(2) th:nth-child(12),
body .grp5 table thead tr:nth-child(2) th:last-child{
  border-left:2px solid rgba(255,255,255,0.25) !important;
}

body .grp5 table th.col-round_winner,
body .grp5 table td.col-round_winner{
  position: sticky;
  right: 0;
  z-index: 2;
  background: inherit;
  box-shadow: -8px 0 10px -10px rgba(0,0,0,.35);
}

body .grp5 table td.col-round_winner{
  font-weight:800;
  text-align:center !important;
  white-space:nowrap !important;
  letter-spacing:.2px;
}

body .grp5 table td.col-round_winner:not(:empty){
  background:#f8fafc !important;
  border:1px solid #e5e7eb !important;
}

body .grp5 table td.col-round_winner.is-tie,
body .grp5 table td.col-round_winner[data-winner="TIE"]{
  color:#111827 !important;
  background:#f3f4f6 !important;
  border-color:#e5e7eb !important;
}

body .grp5 table td.col-round_winner.is-blue,
body .grp5 table td.col-round_winner[data-winner-colour="blue"]{
  color:#1d4ed8 !important;
  background:#eff6ff !important;
  border-color:#bfdbfe !important;
}

body .grp5 table td.col-round_winner.is-green,
body .grp5 table td.col-round_winner[data-winner-colour="green"]{
  color:#15803d !important;
  background:#ecfdf5 !important;
  border-color:#bbf7d0 !important;
}

body .grp5 table td.col-round_winner.is-red,
body .grp5 table td.col-round_winner[data-winner-colour="red"]{
  color:#dc2626 !important;
  background:#fef2f2 !important;
  border-color:#fecaca !important;
}

body .grp5 table td.col-round_winner.is-purple,
body .grp5 table td.col-round_winner[data-winner-colour="purple"]{
  color:#7c3aed !important;
  background:#f5f3ff !important;
  border-color:#ddd6fe !important;
}

body #grp5 .grp5-pager{
  display:flex;
  align-items:center;
  gap:10px;
  margin-top:10px;
  flex-wrap:wrap;
}

body #grp5 .grp5-page{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  padding:8px 12px;
  border:1px solid #d1d5db;
  border-radius:6px;
  background:#fff;
  color:#111827;
  line-height:1;
}

body #grp5 a.grp5-page{
  text-decoration:none;
}

body #grp5 a.grp5-page:hover{
  background:#f3f4f6;
}

body #grp5 .grp5-page.current{
  background:#111827;
  border-color:#111827;
  color:#fff;
  font-weight:700;
  min-width:42px;
}

body #grp5 .grp5-page.of,
body #grp5 .grp5-page.total{
  border:none;
  background:transparent;
  padding:0;
  color:#6b7280;
}

body #grp5 .grp5-page.disabled{
  opacity:.45;
}

#grp5-pager{
  display:flex !important;
  align-items:center !important;
  gap:10px !important;
  flex-wrap:wrap;
  margin-top:10px;
}

#grp5-pager .grp5-page{
  display:inline-flex !important;
  align-items:center !important;
  justify-content:center !important;
  padding:8px 12px !important;
  border:1px solid #d1d5db !important;
  border-radius:6px !important;
  background:#fff !important;
  color:#111827 !important;
  line-height:1 !important;
  margin:0 !important;
  text-decoration:none !important;
}

#grp5-pager .grp5-page.current{
  background:#111827 !important;
  border-color:#111827 !important;
  color:#fff !important;
  font-weight:700 !important;
  min-width:42px;
}

#grp5-pager .grp5-page.of,
#grp5-pager .grp5-page.total{
  border:none !important;
  background:transparent !important;
  padding:0 !important;
  min-width:auto !important;
  color:#6b7280 !important;
}

#grp5-pager .grp5-page.disabled{
  opacity:.45;
}

.history-table tbody tr.is-esr { background: #eef6ff; }
.history-table tbody tr.is-cap { background: #fff7e8; }
.history-table tbody tr.is-esr.is-cap { background: #f3efff; }

.history-table .adj-badge {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 10px;
    font-size: 11px;
    line-height: 1.2;
    border: 1px solid rgba(0,0,0,.12);
    background: #fff;
    color: #333;
}
