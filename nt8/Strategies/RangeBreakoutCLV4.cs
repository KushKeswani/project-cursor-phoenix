#region Using declarations
using NinjaTrader.NinjaScript;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class RangeBreakoutCLV4 : RangeBreakoutStrategyV4
    {
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                base.OnStateChange();
                Instrument = InstrumentPreset.CL;
                Name = "RangeBreakout CL";
                RangeStartHour = 9; RangeStartMinute = 0; RangeEndHour = 9; RangeEndMinute = 30;
                TradeStartHour = 10; TradeStartMinute = 30; TradeEndHour = 12; TradeEndMinute = 30;
                CloseAllHour = 16; CloseAllMinute = 55;
            }
            else base.OnStateChange();
        }
    }
}
