using System;
using System.Collections.Generic;
using System.Text;
using System.Windows.Forms;
using System.Drawing;
using System.Drawing.Drawing2D;

namespace AutoMationTest.UI
{
    public class JianBianPanel : Panel
    {
        public JianBianPanel()
        {
            this.SetStyle(ControlStyles.UserPaint, true);
            this.SetStyle(ControlStyles.ResizeRedraw, true);
            this.SetStyle(ControlStyles.AllPaintingInWmPaint, true);
            this.SetStyle(ControlStyles.OptimizedDoubleBuffer, true);
        }

        private Color _centetco = Color.WhiteSmoke;
        public Color CenterColor
        {
            get
            {
                return _centetco;
            }
            set
            {
                _centetco = value;
            }
        }

        private Color _surrodco = Color.LightGray;
        public Color SurroundColor
        {
            get
            {
                return _surrodco;
            }
            set
            {
                _surrodco = value;
            }
        }

        protected override void OnPaintBackground(PaintEventArgs e)
        {
            Point[] points = { new Point(0, 0), new Point(0, this.Height), new Point(this.Width, this.Height), new Point(this.Width, 0), };

            Color[] colors = { SurroundColor };
            PathGradientBrush pbrush = new PathGradientBrush(points);
            pbrush.CenterColor = CenterColor;
            pbrush.SurroundColors = colors;
            e.Graphics.FillRectangle(pbrush, e.ClipRectangle);

            //base.OnPaintBackground(e);
        }


    }
}
