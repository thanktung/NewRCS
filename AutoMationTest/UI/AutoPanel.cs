using System;
using System.Collections.Generic;
//using System.Linq;
using System.Text;
using System.Windows.Forms;
using System.Drawing;

namespace AutoMationTest.UI
{
    public class AutoPanel : Panel
    {
        //protected override CreateParams CreateParams
        //{
        //    get
        //    {
        //        var cp = base.CreateParams;
        //        cp.Style &= ~0x02000000;
        //        return cp;
        //    }
        //}

        protected override Point ScrollToControl(Control activeControl)
        {
            return this.AutoScrollPosition;
        }

        public AutoPanel()
            : base()
        {
            base.SetStyle(ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint, true);
            base.UpdateStyles();

            this.AutoScroll = true;
        }
    }
}
