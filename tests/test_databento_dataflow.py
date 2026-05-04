import zipfile

import zstandard as zstd

from tradingagents.dataflows import databento


def _write_bar_zip(path, rows):
    csv = "ts_event,open,high,low,close,volume,symbol\n" + "\n".join(rows) + "\n"
    compressed = zstd.ZstdCompressor().compress(csv.encode("utf-8"))
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("glbx-mdp3-20100606-20260427.ohlcv-1m.csv.zst", compressed)


def _write_mbp_zip(path, rows):
    csv = (
        "ts_event,price,size,bid_px_00,ask_px_00,bid_sz_00,ask_sz_00,bid_ct_00,ask_ct_00,symbol\n"
        + "\n".join(rows)
        + "\n"
    )
    compressed = zstd.ZstdCompressor().compress(csv.encode("utf-8"))
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("glbx-mdp3-20260427.mbp-1.csv.zst", compressed)


def test_get_stock_data_reads_databento_zip(tmp_path, monkeypatch):
    archive_path = tmp_path / "bars.zip"
    _write_bar_zip(
        archive_path,
        [
            "2026-04-27T00:00:00.000000000Z,100,101,99,100.5,10,NQM6",
            "2026-04-27T00:01:00.000000000Z,100.5,102,100,101.5,20,NQM6",
            "2026-04-27T00:00:00.000000000Z,200,201,199,200.5,30,ESM6",
        ],
    )
    monkeypatch.setenv("DATABENTO_BAR_ZIP", str(archive_path))

    result = databento.get_stock_data("NQM6", "2026-04-27", "2026-04-28")

    assert "# Total records: 2" in result
    assert "2026-04-27 00:00:00,100.0,101,99,100.5,10" in result
    assert "ESM6" not in result


def test_get_indicator_reads_databento_zip(tmp_path, monkeypatch):
    archive_path = tmp_path / "bars.zip"
    rows = [
        f"2026-04-27T00:{minute:02d}:00.000000000Z,{100+minute},{101+minute},{99+minute},{100.5+minute},10,NQM6"
        for minute in range(20)
    ]
    _write_bar_zip(archive_path, rows)
    monkeypatch.setenv("DATABENTO_BAR_ZIP", str(archive_path))

    result = databento.get_indicator("NQM6", "rsi", "2026-04-27", 1)

    assert "## rsi values for NQM6" in result
    assert "Date,rsi" in result


def test_get_orderbook_microstructure_reads_mbp_zip(tmp_path, monkeypatch):
    archive_path = tmp_path / "ticks.zip"
    _write_mbp_zip(
        archive_path,
        [
            "2026-04-26T23:59:00.000000000Z,99,1,98,100,1,1,1,1,NQM6",
            "2026-04-27T00:00:00.000000000Z,100,1,99,101,3,1,1,1,NQM6",
            "2026-04-27T00:01:00.000000000Z,101,1,100,102,1,3,1,1,NQM6",
            "2026-04-27T00:00:00.000000000Z,200,1,199,201,5,5,1,1,ESM6",
        ],
    )
    monkeypatch.setenv("DATABENTO_TICK_ZIP", str(archive_path))

    result = databento.get_orderbook_microstructure("NQM6", "2026-04-27", "2026-04-28", "5min")

    assert "# Databento GLBX.MDP3 mbp-1 microstructure for NQM6" in result
    assert "quote_count" in result
    assert "2026-04-26" not in result
    assert "200" not in result
