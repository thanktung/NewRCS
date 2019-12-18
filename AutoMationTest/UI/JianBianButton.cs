using System;
using System.Collections.Generic;
using System.Text;
using System.Windows.Forms;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.ComponentModel;

namespace AutoMationTest.UI
{
    public class JianBianButton : Button
    {
        public JianBianButton()
        {
            this.SetStyle(ControlStyles.UserPaint, true);
            this.SetStyle(ControlStyles.ResizeRedraw, true);
            this.SetStyle(ControlStyles.AllPaintingInWmPaint, true);
            this.SetStyle(ControlStyles.OptimizedDoubleBuffer, true);
            this.SetStyle(ControlStyles.SupportsTransparentBackColor, true);
        }

        private Color _centetco = Color.White ;
        [RefreshProperties(RefreshProperties.Repaint)]
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

        private Color _surrodco = Color.Gray;
        [RefreshProperties(RefreshProperties.Repaint)]
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

        protected override void OnPaint(PaintEventArgs e)
        {
            Point[] points = { new Point(0, 0), new Point(0, this.Height), new Point(this.Width, this.Height), new Point(this.Width, 0), };

            Color[] colors = { SurroundColor };
            PathGradientBrush pbrush = new PathGradientBrush(points);
            pbrush.CenterColor = CenterColor;
            pbrush.SurroundColors = colors;
            e.Graphics.FillRectangle(pbrush, e.ClipRectangle);

            StringFormat sf = new StringFormat();
            sf.Alignment = StringAlignment.Center;
            sf.LineAlignment = StringAlignment.Center;

            SolidBrush sb = new SolidBrush(this.ForeColor);
            e.Graphics.DrawString(this.Text, this.Font, sb, e.ClipRectangle, sf);
            //base.OnPaintBackground(e);
        }



    }
}
