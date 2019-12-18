using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Data;
using System.Linq;
using System.Text;
using System.Windows.Forms;

namespace AutoMationTest.UI
{
    /// <summary>
    /// 
    /// </summary>
    [DefaultEvent("Click")]
    public partial class UserSwitch : UserControl
    {
        /// <summary>
        ///
        /// </summary>
        public UserSwitch()
        {
            InitializeComponent();
            DoubleBuffered = true;
            brush_switch_background = new SolidBrush(color_switch_background);
            pen_switch_background = new Pen(color_switch_background, 2f);
            brush_switch_foreground = new SolidBrush(color_switch_foreground);

            centerFormat = new StringFormat();
            centerFormat.Alignment = StringAlignment.Center;
            centerFormat.LineAlignment = StringAlignment.Center;
        }

        private void UserSwitch_Load(object sender, EventArgs e)
        {

        }

        private void UserSwitch_Paint(object sender, PaintEventArgs e)
        {
            e.Graphics.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.HighQuality;
            e.Graphics.TextRenderingHint = System.Drawing.Text.TextRenderingHint.ClearTypeGridFit;

            Point center = GetCenterPoint();
            e.Graphics.TranslateTransform(center.X, center.Y);

            int radius = 45 * (center.X * 2 - 30) / 100;
            if (radius < 5) return;

            Rectangle rectangle_larger = new Rectangle(-radius - 4, -radius - 4, 2 * radius + 8, 2 * radius + 8);
            Rectangle rectangle = new Rectangle(-radius, -radius, 2 * radius, 2 * radius);

            e.Graphics.DrawEllipse(pen_switch_background, rectangle_larger);

            e.Graphics.FillEllipse(brush_switch_background, rectangle);//brush_switch_background
            //}
            //else
            //{
            //    e.Graphics.FillEllipse(new SolidBrush(Color.Tomato), rectangle);
            //}

            float angle = (-1) * Angle;

            if (SwitchStatus) angle = Angle;

            e.Graphics.RotateTransform(angle);
            int temp = 25 * (center.X * 2 - 30) / 100;
            Rectangle rect_switch = new Rectangle(-center.X / 6, -radius - temp, center.X / 3, radius * 2 + temp * 2);
            e.Graphics.FillRectangle(brush_switch_foreground, rect_switch);

            Rectangle rect_mini = new Rectangle(-center.X / 10, -radius - 4, center.X / 5, center.X * 3 / 6);
            e.Graphics.FillEllipse(SwitchStatus ? Brushes.Lime : Brushes.Tomato, rect_mini);

            if (ShowText)
            {
                Rectangle rect_text = new Rectangle(-50, -radius - temp - 12, 100, 15);
                e.Graphics.DrawString(SwitchStatus ? description[1] : description[0], Font, SwitchStatus ? Brushes.LimeGreen : Brushes.Tomato, rect_text, centerFormat);
            }
            e.Graphics.ResetTransform();
        }





        #region Private Member

        private Color color_switch_background = Color.DimGray;
        private Brush brush_switch_background = null;
        private Pen pen_switch_background = null;
        private bool switch_status = false;
        private Color color_switch_foreground = Color.FromArgb(36, 36, 36);
        private Brush brush_switch_foreground = null;
        private StringFormat centerFormat = null;
        private string[] description = new string[2] { "Off", "On" };
        private string _offstr = "Off";
        private string _onstr = "On";
        private float _angle = 45;
        private bool bshowtext = true;

        #endregion

        #region Event Handle

        /// <summary>
        ///點擊了按鈕開關後觸發
        /// </summary>
        [Category("操作")]
        [Description("點擊了按鈕開關後觸發")]
        public event Action<object, bool> OnSwitchChanged;

        #endregion

        #region Private Method

        private Point GetCenterPoint()
        {
            if (Height > Width)
            {
                return new Point(Width / 2, Width / 2);
            }
            else
            {
                return new Point(Height / 2, Height / 2);
            }
        }

        #endregion

        #region Public Member

        /// <summary>
        /// 獲取或設置開關的关闭字符
        /// </summary>
        [Browsable(true)]
        [Description("獲取或設置開關关闭时的字符")]
        [Category("外觀")]
        [DefaultValue("Off")]
        public string OffString
        {
            get
            {
                return _offstr;
            }
            set
            {
                _offstr = value;
                description[0] = _offstr;
                Invalidate();
            }
        }

        /// <summary>
        /// 獲取或設置開關的关闭字符
        /// </summary>
        [Browsable(true)]
        [Description("獲取或設置開關开启时的字符")]
        [Category("外觀")]
        [DefaultValue("On")]
        public string OnString
        {
            get
            {
                return _onstr;
            }
            set
            {
                _onstr = value;
                description[1] = _onstr;
                Invalidate();
            }
        }

        /// <summary>
        /// 獲取或設置開關的开关角度
        /// </summary>
        [Browsable(true)]
        [Description("獲取或設置開關的开关角度")]
        [Category("外觀")]
        [DefaultValue((float)45)]
        public float Angle
        {
            get
            {
                return _angle;
            }
            set
            {
                _angle = value;

                Invalidate();
            }
        }

        /// <summary>
        /// 獲取或設置開關的开关角度
        /// </summary>
        [Browsable(true)]
        [Description("獲取或設置開關的字符是否显示")]
        [Category("外觀")]
        [DefaultValue((bool)true)]
        public bool ShowText
        {
            get
            {
                return bshowtext;
            }
            set
            {
                bshowtext = value;

                Invalidate();
            }
        }

        /// <summary>
        /// 獲取或設置開關的背景色
        /// </summary>
        [Browsable(true)]
        [Description("獲取或設置開關的背景色")]
        [Category("外觀")]
        [DefaultValue(typeof(Color), "DimGray")]
        public Color SwitchBackground
        {
            get
            {
                return color_switch_background;
            }
            set
            {
                color_switch_background = value;
                brush_switch_background.Dispose();
                pen_switch_background.Dispose();
                brush_switch_background = new SolidBrush(color_switch_background);
                pen_switch_background = new Pen(color_switch_background, 2f);
                Invalidate();
            }
        }

        /// <summary>
        ///獲取或設置開關的前景色
        /// </summary>
        [Browsable(true)]
        [Description("獲取或設置開關的前景色")]
        [Category("外觀")]
        [DefaultValue(typeof(Color), "[36, 36, 36]")]
        public Color SwitchForeground
        {
            get
            {
                return color_switch_foreground;
            }
            set
            {
                color_switch_foreground = value;
                brush_switch_foreground = new SolidBrush(color_switch_foreground);
                Invalidate();
            }
        }


        /// <summary>
        /// 獲取或設置開關的開合狀態
        /// </summary>
        [Browsable(true)]
        [Description("獲取或設置開關的開合狀態")]
        [Category("外觀")]
        [DefaultValue(false)]
        public bool SwitchStatus
        {
            get
            {
                return switch_status;
            }
            set
            {
                if (value != switch_status)
                {
                    switch_status = value;
                    Invalidate();
                    if (OnSwitchChanged != null)
                    {
                        OnSwitchChanged.Invoke(this, switch_status);
                    }
                }
            }
        }


        /// <summary>
        /// 例如：new string[]{"Off","On"}
        /// </summary>
        [Browsable(false)]
        public string[] SwitchStatusDescription
        {
            get { return description; }
            set
            {
                if (value.Length == 2)
                {
                    description = value;
                }
            }
        }

        #endregion

        private void UserSwitch_Click(object sender, EventArgs e)
        {
            SwitchStatus = !SwitchStatus;
        }
    }
}
