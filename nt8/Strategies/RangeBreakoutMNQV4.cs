#region Using declarations
using NinjaTrader.NinjaScript;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class RangeBreakoutMNQV4 : RangeBreakoutStrategyV4
    {
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                base.OnStateChange();
                Instrument = InstrumentPreset.MNQ;
                Name = "RangeBreakout MNQ";
                RangeStartHour = 9; RangeStartMinute = 35; RangeEndHour = 9; RangeEndMinute = 55;
                TradeStartHour = 11; TradeStartMinute = 0; TradeEndHour = 13; TradeEndMinute = 0;
                CloseAllHour = 16; CloseAllMinute = 55;
            }
            else base.OnStateChange();
        }
    }
}
