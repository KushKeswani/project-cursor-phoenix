#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
#endregion

// V4: V3 + Trade window, Close-all time, Contracts, Max entries per day. See docs/NT8_V4_PROPOSAL.md.

namespace NinjaTrader.NinjaScript.Strategies
{
    public class RangeBreakoutStrategyV4 : Strategy
    {
        public enum InstrumentPreset { CL, MGC, MNQ, YM }

        #region Parameters

        [NinjaScriptProperty]
        [Display(Name = "Instrument Preset", Order = 1, GroupName = "Config")]
        public InstrumentPreset Instrument { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Export Trades to CSV", Order = 2, GroupName = "Config")]
        public bool ExportTradesToCsv { get; set; }

        [NinjaScriptProperty]
        [Range(-360, 360)]
        [Display(Name = "Timezone Offset (minutes)", Order = 3, GroupName = "Config")]
        public int TimezoneOffsetMinutes { get; set; }

        [Browsable(false)]
        public int RangeStartHour { get; set; }

        [Browsable(false)]
        public int RangeStartMinute { get; set; }

        [Browsable(false)]
        public int RangeEndHour { get; set; }

        [Browsable(false)]
        public int RangeEndMinute { get; set; }

        [Browsable(false)]
        public bool UseCustomSession { get; set; }

        [Browsable(false)]
        public int SessionStartHour { get; set; }

        [Browsable(false)]
        public int SessionStartMinute { get; set; }

        [Browsable(false)]
        public int SessionEndHour { get; set; }

        [Browsable(false)]
        public int SessionEndMinute { get; set; }

        [Browsable(false)]
        public int TradeStartHour { get; set; }

        [Browsable(false)]
        public int TradeStartMinute { get; set; }

        [Browsable(false)]
        public int TradeEndHour { get; set; }

        [Browsable(false)]
        public int TradeEndMinute { get; set; }

        [Browsable(false)]
        public int CloseAllHour { get; set; }

        [Browsable(false)]
        public int CloseAllMinute { get; set; }

        [NinjaScriptProperty]
        [Range(1, 10)]
        [Display(Name = "Contracts", Order = 21, GroupName = "Config")]
        public int Contracts { get; set; }

        [NinjaScriptProperty]
        [Range(0, 5)]
        [Display(Name = "Max entries per day", Order = 22, GroupName = "Config", Description = "0 = use instrument default.")]
        public int MaxEntriesPerDay { get; set; }

        #endregion

        #region State

        private double _tickSize;
        private bool _firstBarLogged;
        private int _barMinutes;
        private int _sessionStartMin, _sessionEndMin;
        private int _rangeStartMin, _rangeEndMin, _tradeStartMin, _tradeEndMin, _closeAllMin;
        private double _slPts, _ptPts, _offsetPts, _beAfterPts, _beOffsetPts;
        private double _trailByPts, _trailStartPts, _trailFreqPts;
        private bool _breakevenOn, _trailOn, _atrAdaptive;
        private double _slAtrMult, _ptAtrMult, _trailAtrMult;
        private int _maxEntriesPerDay;
        private int _quantity;
        private HashSet<DayOfWeek> _excludedWeekdays;

        private double _rangeHigh = double.NegativeInfinity;
        private double _rangeLow = double.PositiveInfinity;
        private bool _rangeReady, _buildingRange;
        private bool _longArmed, _shortArmed, _cooldown;
        private int _entriesToday;
        private DateTime _currentDate = DateTime.MinValue;

        private bool _isLong;
        private double _entryPrice, _stopPrice, _ptPrice, _bestPrice;
        private bool _beApplied;
        private double _longLevel, _shortLevel;
        private double _dayAtr;

        private ATR _atrIndicator;
        private string _exportPath;
        private System.IO.StreamWriter _exportWriter;
        private double _lastEntryPrice;
        private DateTime _lastEntryTime;
        private bool _lastEntryWasLong;

        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Instrument = InstrumentPreset.MNQ;
                ExportTradesToCsv = false;
                TimezoneOffsetMinutes = 0;
                RangeStartHour = 9;
                RangeStartMinute = 35;
                RangeEndHour = 9;
                RangeEndMinute = 55;
                UseCustomSession = false;
                SessionStartHour = 8;
                SessionStartMinute = 0;
                SessionEndHour = 18;
                SessionEndMinute = 0;
                TradeStartHour = 11;
                TradeStartMinute = 0;
                TradeEndHour = 13;
                TradeEndMinute = 0;
                CloseAllHour = 16;
                CloseAllMinute = 55;
                Contracts = 1;
                MaxEntriesPerDay = 0;
                Name = $"RangeBreakout {Instrument}";
                Calculate = Calculate.OnBarClose;
                BarsRequiredToTrade = 1;
                IsUnmanaged = false;
            }
            else if (State == State.DataLoaded)
            {
                LoadInstrumentConfig();
                _atrIndicator = ATR(14);
                _firstBarLogged = false;
            }
            else if (State == State.Terminated)
            {
                _exportWriter?.Dispose();
            }
        }

        private double GetTickValue()
        {
            switch (Instrument)
            {
                case InstrumentPreset.CL: return 10.0;
                case InstrumentPreset.MGC: return 1.0;
                case InstrumentPreset.MNQ: return 0.5;
                case InstrumentPreset.YM: return 5.0;
                default: return 1.0;
            }
        }

        private void LoadInstrumentConfig()
        {
            _tickSize = TickSize;
            _barMinutes = (BarsPeriod.BarsPeriodType == BarsPeriodType.Minute) ? (int)BarsPeriod.Value : 5;
            if (_barMinutes < 1) _barMinutes = 5;

            switch (Instrument)
            {
                case InstrumentPreset.CL:
                    _sessionStartMin = 8 * 60;
                    _sessionEndMin = 18 * 60;
                    _rangeStartMin = 9 * 60 + 0;
                    _rangeEndMin = 9 * 60 + 30;
                    _tradeStartMin = 10 * 60 + 30;
                    _tradeEndMin = 12 * 60 + 30;
                    _closeAllMin = 16 * 60 + 55;
                    _slPts = 45 * _tickSize;
                    _ptPts = 135 * _tickSize;
                    _offsetPts = 0;
                    _breakevenOn = true;
                    _beAfterPts = 30 * _tickSize;
                    _beOffsetPts = 4 * _tickSize;
                    _trailOn = true;
                    _trailByPts = 10 * _tickSize;
                    _trailStartPts = 15 * _tickSize;
                    _trailFreqPts = 5 * _tickSize;
                    _maxEntriesPerDay = 2;
                    _atrAdaptive = false;
                    break;
                case InstrumentPreset.MGC:
                    _sessionStartMin = 8 * 60;
                    _sessionEndMin = 17 * 60;
                    _rangeStartMin = 9 * 60 + 0;
                    _rangeEndMin = 9 * 60 + 30;
                    _tradeStartMin = 12 * 60 + 0;
                    _tradeEndMin = 13 * 60 + 0;
                    _closeAllMin = 16 * 60 + 55;
                    _offsetPts = 15 * _tickSize;
                    _breakevenOn = false;
                    _trailOn = true;
                    _trailByPts = 1.2 * _tickSize;
                    _trailStartPts = 999 * _tickSize;
                    _trailFreqPts = 50 * _tickSize;
                    _maxEntriesPerDay = 1;
                    _atrAdaptive = true;
                    _slAtrMult = 1.0;
                    _ptAtrMult = 3.0;
                    _trailAtrMult = 1.2;
                    break;
                case InstrumentPreset.MNQ:
                    _sessionStartMin = 8 * 60;
                    _sessionEndMin = 18 * 60;
                    _rangeStartMin = 9 * 60 + 35;
                    _rangeEndMin = 9 * 60 + 55;
                    _tradeStartMin = 11 * 60 + 0;
                    _tradeEndMin = 13 * 60 + 0;
                    _closeAllMin = 16 * 60 + 55;
                    _slPts = 80 * _tickSize;
                    _ptPts = 240 * _tickSize;
                    _offsetPts = 2 * _tickSize;
                    _breakevenOn = false;
                    _trailOn = false;
                    _trailByPts = 10 * _tickSize;
                    _trailStartPts = 999 * _tickSize;
                    _trailFreqPts = 10 * _tickSize;
                    _maxEntriesPerDay = 2;
                    _atrAdaptive = false;
                    break;
                case InstrumentPreset.YM:
                    _sessionStartMin = 8 * 60;
                    _sessionEndMin = 18 * 60;
                    _rangeStartMin = 9 * 60 + 0;
                    _rangeEndMin = 9 * 60 + 30;
                    _tradeStartMin = 11 * 60 + 0;
                    _tradeEndMin = 13 * 60 + 0;
                    _closeAllMin = 16 * 60 + 55;
                    _slPts = 25 * _tickSize;
                    _ptPts = 75 * _tickSize;
                    _offsetPts = 5 * _tickSize;
                    _breakevenOn = true;
                    _beAfterPts = 82 * _tickSize;
                    _beOffsetPts = 1 * _tickSize;
                    _trailOn = true;
                    _trailByPts = 25 * _tickSize;
                    _trailStartPts = 31 * _tickSize;
                    _trailFreqPts = 5 * _tickSize;
                    _maxEntriesPerDay = 2;
                    _atrAdaptive = false;
                    break;
            }

            _rangeStartMin = RangeStartHour * 60 + RangeStartMinute;
            _rangeEndMin = RangeEndHour * 60 + RangeEndMinute;

            _tradeStartMin = TradeStartHour * 60 + TradeStartMinute;
            _tradeEndMin = TradeEndHour * 60 + TradeEndMinute;
            _closeAllMin = CloseAllHour * 60 + CloseAllMinute;
            _quantity = Math.Max(1, Math.Min(10, Contracts));
            if (MaxEntriesPerDay > 0)
                _maxEntriesPerDay = MaxEntriesPerDay;

            if (UseCustomSession)
            {
                _sessionStartMin = SessionStartHour * 60 + SessionStartMinute;
                _sessionEndMin = SessionEndHour * 60 + SessionEndMinute;
            }

            _excludedWeekdays = new HashSet<DayOfWeek> { DayOfWeek.Saturday, DayOfWeek.Sunday };
            _lastEntryPrice = 0;

            if (ExportTradesToCsv)
            {
                string dir = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "NinjaTrader 8", "RangeBreakoutTrades");
                System.IO.Directory.CreateDirectory(dir);
                _exportPath = System.IO.Path.Combine(dir, $"{Instrument}_nt8_trades_{DateTime.Now:yyyyMMdd_HHmmss}.csv");
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade) return;

            // NT8 stamps bars with bar end time; Python uses bar start (left-labeled). Derive bar start for alignment.
            DateTime barEnd = Time[0];
            DateTime barStart = barEnd.AddMinutes(-_barMinutes);

            // Debug: log first bar to verify session includes 8am (needed for range building)
            if (!_firstBarLogged)
            {
                Print($"[{Instrument}] First bar: end={barEnd:yyyy-MM-dd HH:mm}, start={barStart:HH:mm} (need 8:00 for range)");
                _firstBarLogged = true;
            }
            int barMin = barStart.Hour * 60 + barStart.Minute + TimezoneOffsetMinutes;
            if (barMin < 0) barMin += 1440;
            if (barMin >= 1440) barMin -= 1440;

            if (barMin < _sessionStartMin || barMin >= _sessionEndMin) return;

            var barDate = barStart.Date;
            var wd = barStart.DayOfWeek;
            // Assumes single primary series; last bar in Bars is treated as last bar of date.
            bool isLastBarOfDate = (CurrentBar >= Bars.Count - 1);

            if (barDate != _currentDate)
            {
                if (Position.MarketPosition != MarketPosition.Flat && _currentDate != DateTime.MinValue)
                    FlattenPosition();
                _currentDate = barDate;
                _rangeHigh = double.NegativeInfinity;
                _rangeLow = double.PositiveInfinity;
                _rangeReady = false;
                _buildingRange = false;
                _longArmed = _shortArmed = false;
                _cooldown = false;
                _entriesToday = 0;
            }

            if (_excludedWeekdays.Contains(wd)) return;

            bool shouldFlatten = (barMin >= _closeAllMin || barMin + _barMinutes >= _closeAllMin) || isLastBarOfDate;
            if (shouldFlatten)
            {
                if (Position.MarketPosition != MarketPosition.Flat)
                    FlattenPosition();
                _longArmed = _shortArmed = false;
                _cooldown = false;
                return;
            }

            if (_rangeStartMin <= barMin && barMin < _rangeEndMin)
            {
                _buildingRange = true;
                if (High[0] > _rangeHigh) _rangeHigh = High[0];
                if (Low[0] < _rangeLow) _rangeLow = Low[0];
                return;
            }

            if (_buildingRange && barMin >= _rangeEndMin)
            {
                if (_rangeHigh > double.NegativeInfinity)
                {
                    _rangeReady = true;
                    _longArmed = _shortArmed = true;
                    if (_atrAdaptive)
                    {
                        _dayAtr = _atrIndicator[0];
                        if (double.IsNaN(_dayAtr) || _dayAtr < _tickSize)
                            _dayAtr = (_rangeHigh > _rangeLow) ? (_rangeHigh - _rangeLow) : _tickSize;
                        _slPts = _slAtrMult * _dayAtr;
                        _ptPts = _ptAtrMult * _dayAtr;
                        _trailByPts = _trailAtrMult * _dayAtr;
                        _trailStartPts = _trailByPts * 1.05 + 5 * _tickSize;
                    }
                }
                _buildingRange = false;
            }

            if (!_rangeReady) return;
            if (barMin < _tradeStartMin || barMin >= _tradeEndMin) return;

            _longLevel = _rangeHigh + _offsetPts;
            _shortLevel = _rangeLow - _offsetPts;

            if (Position.MarketPosition != MarketPosition.Flat)
            {
                ProcessPosition(barStart);
                return;
            }

            if (_cooldown)
            {
                _cooldown = false;
                if (!_longArmed && Close[0] < _longLevel) _longArmed = true;
                if (!_shortArmed && Close[0] > _shortLevel) _shortArmed = true;
                return;
            }

            if (!_longArmed && Low[0] < _longLevel) _longArmed = true;
            if (!_shortArmed && High[0] > _shortLevel) _shortArmed = true;

            if (_entriesToday >= _maxEntriesPerDay) return;

            bool longHit = _longArmed && High[0] >= _longLevel;
            bool shortHit = _shortArmed && Low[0] <= _shortLevel;

            if (longHit && shortHit)
            {
                if (Open[0] >= _longLevel)
                    EnterLong();
                else if (Open[0] <= _shortLevel)
                    EnterShort();
                else if ((_longLevel - Open[0]) <= (Open[0] - _shortLevel))
                    EnterLong();
                else
                    EnterShort();
            }
            else if (longHit)
                EnterLong();
            else if (shortHit)
                EnterShort();
        }

        private void EnterLong()
        {
            EnterLongStopMarket(0, true, _quantity, _longLevel, "Long");
            _entriesToday++;
            _longArmed = false;
        }

        private void EnterShort()
        {
            EnterShortStopMarket(0, true, _quantity, _shortLevel, "Short");
            _entriesToday++;
            _shortArmed = false;
        }

        private void ProcessPosition(DateTime barTime)
        {
            if (Position.MarketPosition == MarketPosition.Flat) return;

            _isLong = Position.MarketPosition == MarketPosition.Long;
            _entryPrice = Position.AveragePrice;
            if (_bestPrice == 0) _bestPrice = _entryPrice;

            if (_isLong)
            {
                if (High[0] > _bestPrice) _bestPrice = High[0];
                _stopPrice = _entryPrice - _slPts;
                _ptPrice = _entryPrice + _ptPts;

                if (Low[0] <= _stopPrice)
                {
                    ExitLong("SL");
                    SetArmedFromExit();
                    ResetPositionState();
                    return;
                }
                if (High[0] >= _ptPrice)
                {
                    ExitLongLimit(0, true, _quantity, _ptPrice, "PT", "Long");
                    SetArmedFromExit();
                    ResetPositionState();
                    return;
                }

                double move = _bestPrice - _entryPrice;
                if (_breakevenOn && !_beApplied && move >= _beAfterPts)
                {
                    double newStop = _entryPrice + _beOffsetPts;
                    if (newStop > _stopPrice) _stopPrice = newStop;
                    _beApplied = true;
                }
                if (_trailOn && move >= _trailStartPts)
                {
                    double trailStop = _bestPrice - _trailByPts;
                    if (_trailFreqPts > 0)
                        trailStop = _entryPrice + (int)((trailStop - _entryPrice) / _trailFreqPts) * _trailFreqPts;
                    if (trailStop > _stopPrice) _stopPrice = trailStop;
                }
            }
            else
            {
                if (Low[0] < _bestPrice) _bestPrice = Low[0];
                _stopPrice = _entryPrice + _slPts;
                _ptPrice = _entryPrice - _ptPts;

                if (High[0] >= _stopPrice)
                {
                    ExitShort("SL");
                    SetArmedFromExit();
                    ResetPositionState();
                    return;
                }
                if (Low[0] <= _ptPrice)
                {
                    ExitShortLimit(0, true, _quantity, _ptPrice, "PT", "Short");
                    SetArmedFromExit();
                    ResetPositionState();
                    return;
                }

                double move = _entryPrice - _bestPrice;
                if (_breakevenOn && !_beApplied && move >= _beAfterPts)
                {
                    double newStop = _entryPrice - _beOffsetPts;
                    if (newStop < _stopPrice) _stopPrice = newStop;
                    _beApplied = true;
                }
                if (_trailOn && move >= _trailStartPts)
                {
                    double trailStop = _bestPrice + _trailByPts;
                    if (_trailFreqPts > 0)
                        trailStop = _entryPrice - (int)((_entryPrice - trailStop) / _trailFreqPts) * _trailFreqPts;
                    if (trailStop < _stopPrice) _stopPrice = trailStop;
                }
            }
        }

        private void SetArmedFromExit()
        {
            _longArmed = Close[0] < _longLevel;
            _shortArmed = Close[0] > _shortLevel;
            _cooldown = true;
        }

        private void ResetPositionState()
        {
            _bestPrice = 0;
            _beApplied = false;
        }

        private void FlattenPosition()
        {
            if (Position.MarketPosition == MarketPosition.Long)
                ExitLong("Flatten");
            else if (Position.MarketPosition == MarketPosition.Short)
                ExitShort("Flatten");
            ResetPositionState();
        }

        protected override void OnExecutionUpdate(Execution execution, string executionId, double price, int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            if (!ExportTradesToCsv || execution?.Order == null || execution.Order.OrderState != OrderState.Filled) return;

            try
            {
                if (_exportWriter == null)
                {
                    _exportWriter = new System.IO.StreamWriter(_exportPath, false);
                    _exportWriter.WriteLine("entry_ts,exit_ts,instrument,direction,entry_price,exit_price,pnl_ticks,pnl_usd,exit_reason");
                }

                if (execution.IsEntry)
                {
                    _lastEntryPrice = execution.Price;
                    _lastEntryTime = time;
                    _lastEntryWasLong = execution.Order.OrderAction == OrderAction.Buy;
                }
                else if (execution.IsExit && _lastEntryPrice != 0)
                {
                    double tickValue = GetTickValue();
                    double pnlUsd = _lastEntryWasLong
                        ? (execution.Price - _lastEntryPrice) / _tickSize * tickValue
                        : (_lastEntryPrice - execution.Price) / _tickSize * tickValue;
                    double pnlTicks = pnlUsd / tickValue;
                    string dir = _lastEntryWasLong ? "long" : "short";
                    string reason = execution.Order?.Name ?? "";
                    _exportWriter.WriteLine($"{_lastEntryTime:yyyy-MM-dd HH:mm:ss},{time:yyyy-MM-dd HH:mm:ss},{Instrument},{dir},{_lastEntryPrice:F4},{execution.Price:F4},{pnlTicks:F4},{pnlUsd:F2},{reason}");
                    _exportWriter.Flush();
                    _lastEntryPrice = 0;
                }
            }
            catch { }
        }
    }
}
