"use strict";

var CFG = window.CUTGAP_CONFIG || {};
var MAX_LIST = 120;      // 리스트는 잘라서 보여주고 '더 보기'로 늘린다
var MAX_PINS = 250;      // 화면 안 마커 상한. 넘으면 싼 곳부터

var state = {
  sex: "w",
  sort: "price",
  hideVoid: false,
  listLimit: MAX_LIST,
  index: null,
  regionKey: null,
  places: [],
  rows: [],
  hot: null
};

var map = null;
var markers = new Map();
var el = {
  region: document.getElementById("region"),
  list: document.getElementById("list"),
  listTitle: document.getElementById("listTitle"),
  listCount: document.getElementById("listCount"),
  stamp: document.getElementById("stamp"),
  map: document.getElementById("map")
};

/* ── 유틸 ───────────────────────────────────────── */
function won(n) { return n.toLocaleString("ko-KR"); }
function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}
function priceOf(p) { return p[state.sex]; }

/* ── 데이터 ─────────────────────────────────────── */
function loadIndex() {
  return fetch("data/index.json", { cache: "no-cache" })
    .then(function (r) { if (!r.ok) { throw new Error("index.json 없음"); } return r.json(); })
    .then(function (idx) {
      state.index = idx;
      el.region.innerHTML = idx.regions.map(function (r) {
        return '<option value="' + esc(r.key) + '">' + esc(r.region) +
          " (" + r.priced + "/" + r.count + ")</option>";
      }).join("");
      el.stamp.innerHTML = "전국 수집 <span class='num'>" + won(idx.total) +
        "</span>곳 · 가격 확인 <span class='num'>" + won(idx.priced) +
        "</span>곳<br>생성 <span class='num'>" + esc(idx.generated) + "</span>";
      if (!idx.regions.length) { throw new Error("아직 수집된 지역이 없다"); }
      return selectRegion(idx.regions[0].key);
    })
    .catch(function (err) {
      el.stamp.textContent = "데이터 없음";
      el.list.innerHTML = '<div class="empty">데이터를 아직 못 읽었다.<br>' +
        esc(err.message) + "<br>수집기를 한 번 돌리거나 sample 데이터를 넣어라.</div>";
    });
}

function selectRegion(key) {
  state.regionKey = key;
  el.region.value = key;
  return fetch("data/places/" + encodeURIComponent(key) + ".json", { cache: "no-cache" })
    .then(function (r) { if (!r.ok) { throw new Error(key + " 데이터 없음"); } return r.json(); })
    .then(function (shard) {
      state.places = shard.places || [];
      state.listLimit = MAX_LIST;
      var entry = (state.index.regions || []).filter(function (r) { return r.key === key; })[0];
      if (map && entry && entry.cx) {
        map.setCenter(new naver.maps.LatLng(entry.cy, entry.cx));
        map.setZoom(15);
      }
      render();
    })
    .catch(function (err) {
      state.places = [];
      render();
      el.list.innerHTML = '<div class="empty">' + esc(err.message) + "</div>";
    });
}

/* ── 정렬·순위 ──────────────────────────────────── */
function computeRows() {
  var rows = state.places.map(function (p) {
    var cut = priceOf(p);
    return {
      id: p.id, name: p.name || "(이름 없음)", road: p.road || "",
      x: p.x, y: p.y,
      price: cut ? cut.price : null,
      src: cut ? cut.src : null,
      how: cut ? cut.how : null,
      checked: p.checked
    };
  });
  if (state.hideVoid) {
    rows = rows.filter(function (r) { return r.price !== null; });
  }
  rows.sort(function (a, b) {
    if ((a.price === null) !== (b.price === null)) { return a.price === null ? 1 : -1; }
    if (state.sort === "name" || a.price === null) {
      return a.name.localeCompare(b.name, "ko");
    }
    return a.price - b.price;
  });
  var priced = rows.filter(function (r) { return r.price !== null; });
  var cheapest = priced.length ? priced[0].price : null;
  rows.forEach(function (r, i) {
    r.rank = r.price === null ? null : i + 1;
    r.best = r.price !== null && r.price === cheapest;
  });
  state.rows = rows;
}

/* ── 리스트 ─────────────────────────────────────── */
function renderList() {
  var rows = state.rows;
  var sexName = state.sex === "w" ? "여성" : "남성";
  el.listTitle.textContent = sexName + " 커트 · " +
    (state.sort === "price" ? "낮은 가격순" : "이름순");
  var priced = rows.filter(function (r) { return r.price !== null; }).length;
  el.listCount.textContent = won(priced) + "곳 가격 확인 / " + won(rows.length) + "곳";

  if (!rows.length) {
    el.list.innerHTML = '<div class="empty">표시할 미용실이 없다.</div>';
    return;
  }

  var shown = rows.slice(0, state.listLimit);
  var html = shown.map(function (r) {
    var cls = ["card"];
    if (r.price === null) { cls.push("void"); }
    else if (r.best) { cls.push("best"); }
    var srcHtml = r.src
      ? '<span class="src' + (r.how === "neutral" ? " guess" : "") + '">원문 “' +
        esc(r.src) + "”" + (r.how === "neutral" ? " · 성별 구분 없음" : "") + "</span>"
      : '<span class="src">커트 메뉴 없음</span>';
    return '<button type="button" class="' + cls.join(" ") + '" data-id="' + esc(r.id) + '">' +
      '<span class="rank num">' + (r.rank === null ? "–" : r.rank) + "</span>" +
      '<span class="name">' + esc(r.name) +
        (r.best ? '<span class="best-tag">최저가</span>' : "") + "</span>" +
      '<span class="price"><span class="amt num">' +
        (r.price === null ? "가격 미표기" : won(r.price) + '<span class="won">원</span>') +
      '</span><span class="sub">' +
        (r.price === null ? "네이버에서 확인 →" : sexName + " 기준") + "</span></span>" +
      '<span class="meta"><span>' + esc(r.road) + "</span>" + srcHtml + "</span>" +
      "</button>";
  }).join("");

  if (rows.length > state.listLimit) {
    html += '<button type="button" class="more" id="moreBtn">' +
      won(rows.length - state.listLimit) + "곳 더 보기</button>";
  }
  el.list.innerHTML = html;

  var more = document.getElementById("moreBtn");
  if (more) {
    more.addEventListener("click", function () {
      state.listLimit += MAX_LIST * 2;
      renderList();
    });
  }
}

/* ── 지도 ───────────────────────────────────────── */
function pinHtml(r) {
  var cls = "pin" + (r.price === null ? " void" : r.best ? " best" : "") +
    (state.hot === r.id ? " hot" : "");
  var body = r.price === null
    ? '<span class="bub"><b>?</b>미표기</span>'
    : '<span class="bub"><b>' + r.rank + "</b>" + won(r.price) + "<em>원</em></span>";
  return '<div class="' + cls + '" data-id="' + esc(r.id) + '">' + body +
    '<span class="tail"></span></div>';
}

function renderPins() {
  if (!map) { return; }
  var bounds = map.getBounds();
  var visible = [];
  for (var i = 0; i < state.rows.length && visible.length < MAX_PINS; i++) {
    var r = state.rows[i];
    if (r.x == null || r.y == null) { continue; }
    if (bounds && !bounds.hasLatLng(new naver.maps.LatLng(r.y, r.x))) { continue; }
    visible.push(r);
  }
  var keep = new Set(visible.map(function (r) { return r.id; }));
  markers.forEach(function (mk, id) {
    if (!keep.has(id)) { mk.setMap(null); markers.delete(id); }
  });
  visible.forEach(function (r) {
    var icon = { content: pinHtml(r), anchor: new naver.maps.Point(0, 0) };
    var mk = markers.get(r.id);
    if (mk) {
      mk.setIcon(icon);
      return;
    }
    mk = new naver.maps.Marker({
      map: map,
      position: new naver.maps.LatLng(r.y, r.x),
      icon: icon,
      zIndex: r.best ? 100 : (r.price === null ? 1 : 10),
      title: r.name
    });
    naver.maps.Event.addListener(mk, "click", function () { openNaver(r.id); });
    markers.set(r.id, mk);
  });
}

function setHot(id) {
  if (state.hot === id) { return; }
  var prev = state.hot;
  state.hot = id;
  [prev, id].forEach(function (key) {
    if (!key) { return; }
    document.querySelectorAll('.card[data-id="' + CSS.escape(key) + '"]').forEach(function (n) {
      n.classList.toggle("hot", key === id);
    });
    var mk = markers.get(key);
    var row = state.rows.filter(function (r) { return r.id === key; })[0];
    if (mk && row) {
      mk.setIcon({ content: pinHtml(row), anchor: new naver.maps.Point(0, 0) });
      mk.setZIndex(key === id ? 200 : (row.best ? 100 : 10));
    }
  });
}

function openNaver(id) {
  window.open("https://map.naver.com/p/entry/place/" + encodeURIComponent(id),
    "_blank", "noopener");
}

function render() {
  computeRows();
  renderList();
  renderPins();
}

/* ── 지도 초기화 ────────────────────────────────── */
function initMap() {
  if (!CFG.mapKeyId) {
    el.map.outerHTML = '<div class="mapmsg">지도 키가 아직 없다.<br>' +
      "네이버 클라우드 플랫폼에서 Maps Key ID를 발급해 <code>docs/config.js</code>의 " +
      "<code>mapKeyId</code>에 넣으면 지도가 나온다.<br>목록은 지도 없이도 그대로 쓸 수 있다.</div>";
    return;
  }
  var s = document.createElement("script");
  s.src = "https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=" +
    encodeURIComponent(CFG.mapKeyId);
  s.onload = function () {
    map = new naver.maps.Map("map", {
      center: new naver.maps.LatLng(37.5665, 126.9780),
      zoom: 15,
      scaleControl: false,
      mapDataControl: false
    });
    naver.maps.Event.addListener(map, "idle", renderPins);
    render();
  };
  s.onerror = function () {
    el.map.innerHTML = '<div class="mapmsg">지도 스크립트를 못 불러왔다. ' +
      "Key ID와 허용 도메인 설정을 확인해라.</div>";
  };
  document.head.appendChild(s);
}

/* ── 이벤트 ─────────────────────────────────────── */
el.region.addEventListener("change", function () { selectRegion(el.region.value); });

document.getElementById("sexSeg").addEventListener("click", function (e) {
  var b = e.target.closest("button");
  if (!b) { return; }
  state.sex = b.dataset.sex;
  this.querySelectorAll("button").forEach(function (x) {
    x.setAttribute("aria-pressed", String(x === b));
  });
  render();
});

document.getElementById("sortSeg").addEventListener("click", function (e) {
  var b = e.target.closest("button");
  if (!b) { return; }
  state.sort = b.dataset.sort;
  this.querySelectorAll("button").forEach(function (x) {
    x.setAttribute("aria-pressed", String(x === b));
  });
  render();
});

document.getElementById("hideVoid").addEventListener("click", function () {
  state.hideVoid = !state.hideVoid;
  this.setAttribute("aria-pressed", String(state.hideVoid));
  render();
});

document.getElementById("near").addEventListener("click", function () {
  var btn = this;
  if (!navigator.geolocation || !state.index) { return; }
  btn.textContent = "찾는 중…";
  navigator.geolocation.getCurrentPosition(function (pos) {
    var best = null, bestD = Infinity;
    state.index.regions.forEach(function (r) {
      if (r.cx == null) { return; }
      var dx = r.cx - pos.coords.longitude, dy = r.cy - pos.coords.latitude;
      var d = dx * dx + dy * dy;
      if (d < bestD) { bestD = d; best = r.key; }
    });
    btn.textContent = "내 위치";
    if (best) { selectRegion(best); }
  }, function () {
    btn.textContent = "내 위치";
    alert("위치를 못 가져왔다. 지역을 직접 골라라.");
  }, { timeout: 8000 });
});

document.addEventListener("pointerover", function (e) {
  if (!e.target || !e.target.closest) { return; }
  var t = e.target.closest("[data-id]");
  if (t) { setHot(t.dataset.id); }
});
document.addEventListener("click", function (e) {
  if (!e.target || !e.target.closest) { return; }
  var card = e.target.closest(".card[data-id]");
  if (card) { openNaver(card.dataset.id); }
});

var issue = document.getElementById("issueLink");
if (CFG.repo) {
  issue.href = "https://github.com/" + CFG.repo +
    "/issues/new?labels=%EC%98%A4%EB%B6%84%EB%A5%98&title=" +
    encodeURIComponent("[오분류] 가게명 / 지역");
}

initMap();
loadIndex();
