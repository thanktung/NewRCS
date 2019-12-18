using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Text;
using System.Windows.Forms;

namespace AutoMationTest.UI
{
    public partial class FrmChangeStatus : Form
    {
        bool bResult = false;
        public string sStatus = "0";
        public FrmChangeStatus(string StationNumber)
        {
            InitializeComponent();
            bResult = false;
            this.comboBox1.Text = "0";
            this.sStatus = "0";
            this.label_Position.Text = StationNumber;
            this.TopMost = true;
        }

        private void FrmChangeStatus_Load(object sender, EventArgs e)
        {

        }

        private void button1_Click(object sender, EventArgs e)
        {
            sStatus = this.comboBox1.SelectedItem.ToString();
            bResult = true;
            this.Close();
        }

        private void button_Close_Click(object sender, EventArgs e)
        {
            bResult = false;
            sStatus = "0";
            this.Close();
        }
    }
}
