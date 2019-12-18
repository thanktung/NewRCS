using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using System.Drawing;

namespace AutoMationTest.UI
{
    public class MyTabControl : TabControl
    {
        protected override void WndProc(ref Message m)
        {
            if (m.Msg == 0x0014)
                return;

            base.WndProc(ref m);
        }


        private Color _BackColor;
        private Color _selectbackcolor = Color.WhiteSmoke;
        private Brush _selectfontcolor = Brushes.Red;
        private Color _tbackcolor = Color.Transparent;
        private Brush _tfontcolor = Brushes.Black;
        private Size _imageSize = new Size(54, 54);

        public MyTabControl()
        {
            this.SetStyle(ControlStyles.UserPaint, true);
            this.SetStyle(ControlStyles.ResizeRedraw, true);
            this.SetStyle(ControlStyles.AllPaintingInWmPaint, true);
            this.SetStyle(ControlStyles.OptimizedDoubleBuffer, true);
            this.SetStyle(ControlStyles.SupportsTransparentBackColor, true);
        }

        public override Color BackColor
        {
            get
            {
                return this._BackColor;
            }
            set
            {
                this._BackColor = value;
            }
        }

        public Color TitileBackColor
        {
            get
            {
                return this._tbackcolor;
            }
            set
            {
                this._tbackcolor = value;
            }
        }

        public Brush TitileFontColor
        {
            get
            {
                return this._tfontcolor;
            }
            set
            {
                this._tfontcolor = value;
            }
        }

        public Color SelectBackColor
        {
            get
            {
                return this._selectbackcolor;
            }
            set
            {
                this._selectbackcolor = value;
            }
        }

        public Brush SelectFontColor
        {
            get
            {
                return this._selectfontcolor;
            }
            set
            {
                this._selectfontcolor = value;
            }
        }

        public Size ImageSize
        {
            get
            {
                return this._imageSize;
            }
            set
            {
                this._imageSize = value;
            }

        }


        protected override void OnPaint(PaintEventArgs e)
        {
            this.DrawTitle(e.Graphics);
            base.OnPaint(e);
        }

        protected virtual void DrawTitle(Graphics g)
        {
            StringFormat sf = new StringFormat();
            sf.Alignment = StringAlignment.Center;
            sf.LineAlignment = StringAlignment.Center;


            using (SolidBrush sb = new SolidBrush(Color.FromArgb(127, 0, 0, 0)))
            {
                for (int i = 0; i < this.TabPages.Count; i++)
                {
                    Rectangle rect = this.GetTabRect(i);
                    Rectangle rect1;
                    Brush bru;

                    if (this.SelectedIndex == i)
                    {
                        sb.Color = this.SelectBackColor;
                        bru = this.SelectFontColor;

                    }
                    else
                    {
                        sb.Color = this.TitileBackColor;
                        bru = this.TitileFontColor;
                    }
                    g.FillRectangle(sb, rect);
                    if (this.ImageList.Images[this.TabPages[i].ImageKey] != null)
                    {
                        g.DrawImage(this.ImageList.Images[this.TabPages[i].ImageKey], rect.X + rect.Width / 2 - this.ImageSize.Width / 2, rect.Y, this.ImageSize.Width, this.ImageSize.Height);
                        rect1 = new Rectangle(rect.X, rect.Y + 27, rect.Width, rect.Height);
                        g.DrawString(this.TabPages[i].Text, this.Font, bru, rect1, sf);
                    }
                    else
                    {
                        rect1 = rect;
                        g.DrawString(this.TabPages[i].Text, this.Font, bru, rect1, sf);
                    }
                }
            }
        }

    }
}
