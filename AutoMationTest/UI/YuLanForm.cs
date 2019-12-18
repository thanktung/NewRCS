using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Data;
using System.Text;
using System.Windows.Forms;
using AutoMationTest.Common;

namespace AutoMationTest.UI
{
    public partial class YuLanForm : UserControl
    {
        public YuLanForm()
        {
            InitializeComponent();
        }

        Button[] YuLan;
        Label[] YulanLabel;
        int SelectNum = 0;

        private void YuLan_Load(object sender, EventArgs e)
        {

        }


        delegate void dSetStation(int stationnum, Color color);
        public void SetStation(int stationnum, Color color)
        {
            try
            {
                if (YuLan[stationnum - 1] != null)
                {
                    if (YuLan[stationnum - 1].InvokeRequired)
                    {
                        dSetStation d = new dSetStation(SetStation);
                        YuLan[stationnum - 1].Invoke(d, new object[] { stationnum, color });
                    }
                    else
                    {
                        if (YuLan[stationnum - 1].BackColor != color)
                        {
                            YuLan[stationnum - 1].BackColor = color;
                            YuLan[stationnum - 1].Refresh();
                            this.Refresh();
                        }
                    }
                }
            }
            catch (Exception ex)
            { }
        }

        public void InitialYuLan()
        {
            YuLan = null;
            YulanLabel = null;
            YuLan = new Button[Produce.Station.Count];
            YulanLabel = new Label[Produce.Station.NameAll.Length];

            int CellWidth = 30;
            int StaY = 0;
            int BigShiftY = 0;

            for (int p = 0; p < Produce.Station.NameAll.Length; p++)
            {
                StaY = 30 + p * 60 + BigShiftY * CellWidth;

                string name = Produce.Station.NameAll[p].ToString();
                int[] List = (int[])Produce.Station.NumberList[name];

                YulanLabel[p] = new Label();
                YulanLabel[p].Text = "[ " + name + " ]";
                YulanLabel[p].Location = new Point(3, StaY - 23);
                YulanLabel[p].ForeColor = Color.DarkCyan;

                autoPanel1.Controls.Add(YulanLabel[p]);

                for (int i = 0; i < List.Length; i++)
                {
                    int shiftX = i % 4;
                    int shiftY = i / 4;

                    YuLan[List[i] - 1] = new Button();
                    YuLan[List[i] - 1].Text = List[i].ToString();
                    YuLan[List[i] - 1].Size = new Size(CellWidth, CellWidth);
                    YuLan[List[i] - 1].FlatStyle = System.Windows.Forms.FlatStyle.Popup;
                    YuLan[List[i] - 1].BackColor = Color.Gray;
                    YuLan[List[i] - 1].ContextMenuStrip = YulanMenu;
                    int X = 5 + (CellWidth + 3) * shiftX;
                    int Y = StaY + (CellWidth + 3) * shiftY;

                    YuLan[List[i] - 1].Location = new Point(X, Y);

                    autoPanel1.Controls.Add(YuLan[List[i] - 1]);
                }

                BigShiftY += (List.Length - 1) / 4;
            }
        }

        private void YulanMenu_Opening(object sender, CancelEventArgs e)
        {
            string number = YulanMenu.SourceControl.Text;
            SelectNum = Convert.ToInt32(number);
            if (Produce.bShowATS[SelectNum - 1])
            {
                隱藏ToolStripMenuItem.Text = "隱藏";
            }
            else
            {
                隱藏ToolStripMenuItem.Text = "顯示";
            }
            if (Produce.bTestGolden[SelectNum - 1])
            {
                測試標準件ToolStripMenuItem.Checked = true;
            }
            else
            {
                測試標準件ToolStripMenuItem.Checked = false;
            }
        }

        private void 隱藏ToolStripMenuItem_Click(object sender, EventArgs e)
        {
            if (隱藏ToolStripMenuItem.Text == "隱藏")
            {
                Produce.bShowATS[SelectNum - 1] = false;
                Produce.SetFixShow(SelectNum, false);
                隱藏ToolStripMenuItem.Text = "顯示";
            }
            else
            {
                Produce.bShowATS[SelectNum - 1] = true;
                Produce.SetFixShow(SelectNum, true);
                隱藏ToolStripMenuItem.Text = "隱藏";
            }
        }

        private void 測試標準件ToolStripMenuItem_Click(object sender, EventArgs e)
        {
            if (!測試標準件ToolStripMenuItem.Checked)
            {
                Produce.bTestGolden[SelectNum - 1] = true;
                測試標準件ToolStripMenuItem.Checked = true;
            }
            else
            {
                Produce.bTestGolden[SelectNum - 1] = false;
                測試標準件ToolStripMenuItem.Checked = false;
            }
        }
    }
}
