using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Data;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using Microsoft.VisualBasic.PowerPacks;

namespace AutoMationTest.UI
{
    public partial class JogWheel : UserControl
    {
        public JogWheel()
        {
            InitializeComponent();
        }
        int loX = 0;
        int loY = 0;
        int loX2 = 0;
        int loY2 = 0;
        public enum Direction
        {
            Left,
            Right,
            Up,
            Down,
            Middle
        }

        public enum Status
        {
            ON,
            OFF
        }
        delegate void dSetOVLocation(OvalShape ovs, int x, int y);
        private void SetOVLocation(OvalShape ovs, int x, int y)
        {
            try
            {
                if (ovs.FindForm().InvokeRequired)
                {
                    dSetOVLocation d = new dSetOVLocation(SetOVLocation);
                    ovs.FindForm().Invoke(d, new object[] { ovs, x, y });
                }
                else
                {
                    if (ovs.Location.X != x || ovs.Location.Y != y)
                    {
                        ovs.Location = new Point(x, y);
                        ovs.Refresh();
                    }
                }
            }
            catch (Exception ex)
            {

            }
        }

        delegate void dSetOVColor(OvalShape ovs, Color surroundcol, Color centrcol);
        private void SetOVColor(OvalShape ovs, Color surroundcol, Color centrcol)
        {
            try
            {
                if (ovs.FindForm().InvokeRequired)
                {
                    dSetOVColor d = new dSetOVColor(SetOVColor);
                    ovs.FindForm().Invoke(d, new object[] { ovs, surroundcol, centrcol });
                }
                else
                {
                    if (ovs.FillColor != surroundcol || ovs.FillGradientColor != centrcol)
                    {
                        ovs.FillColor = surroundcol;
                        ovs.FillGradientColor = centrcol;
                        ovs.BorderColor = surroundcol;
                        ovs.Refresh();
                    }
                }
            }
            catch (Exception ex)
            {

            }
        }

        private void JogWheel_Load(object sender, EventArgs e)
        {
            loX = ov_front.Location.X;
            loY = ov_front.Location.Y;

            loX2 = ov_back.Location.X;
            loY2 = ov_back.Location.Y;
        }

        public void Move(Direction dire)
        {
            switch (dire)
            {
                case Direction.Left:
                    SetOVLocation(ov_front, loX2 + 2, loY);
                    break;

                case Direction.Right:
                    SetOVLocation(ov_front, loX + loX - loX2 - 2, loY);
                    break;

                case Direction.Up:
                    SetOVLocation(ov_front, loX, loY2 + 2);
                    break;

                case Direction.Down:
                    SetOVLocation(ov_front, loX, loY + loY - loY2 - 2);
                    break;

                case Direction.Middle:
                    SetOVLocation(ov_front, loX, loY);
                    break;
            }
        }

        public void ChangeStatus(Status sta)
        {
            switch (sta)
            {
                case Status.ON:
                    SetOVColor(ov_front, Color.DarkRed, Color.WhiteSmoke);
                    break;

                case Status.OFF:
                    SetOVColor(ov_front, Color.Black, Color.WhiteSmoke);
                    break;
            }
        }
    }
}
