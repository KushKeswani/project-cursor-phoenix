#region Using declarations
using NinjaTrader.NinjaScript;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class RangeBreakoutMGCV4 : RangeBreakoutStrategyV4
    {
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                base.OnStateChange();
                Instrument = InstrumentPreset.MGC;
                Name = "RangeBreakout MGC";
                RangeStartHour = 9; RangeStartMinute = 0; RangeEndHour = 9; RangeEndMinute = 30;
                TradeStartHour = 12; TradeStartMinute = 0; TradeEndHour = 13; TradeEndMinute = 0;
                CloseAllHour = 16; CloseAllMinute = 55;
            }
            else base.OnStateChange();
        }
    }
}
