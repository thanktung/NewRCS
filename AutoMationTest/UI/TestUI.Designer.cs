namespace AutoMationTest.UI
{
    partial class TestUI
    {
        /// <summary> 
        /// 必需的设计器变量。
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary> 
        /// 清理所有正在使用的资源。
        /// </summary>
        /// <param name="disposing">如果应释放托管资源，为 true；否则为 false。</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region 组件设计器生成的代码

        /// <summary> 
        /// 设计器支持所需的方法 - 不要
        /// 使用代码编辑器修改此方法的内容。
        /// </summary>
        private void InitializeComponent()
        {
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(TestUI));
            this.panel1 = new System.Windows.Forms.Panel();
            this.panel_connectStatus = new AutoMationTest.UI.JianBianPanel();
            this.checkBox2 = new System.Windows.Forms.CheckBox();
            this.checkBox_Used = new System.Windows.Forms.CheckBox();
            this.UINumber = new System.Windows.Forms.TextBox();
            this.StationName = new System.Windows.Forms.Label();
            this.textBox_TOTAL = new System.Windows.Forms.TextBox();
            this.textBox_NG = new System.Windows.Forms.TextBox();
            this.textBox_YR = new System.Windows.Forms.TextBox();
            this.button1 = new System.Windows.Forms.Button();
            this.textBox_LianxuNG = new System.Windows.Forms.TextBox();
            this.radioButton1 = new System.Windows.Forms.RadioButton();
            this.radioButton2 = new System.Windows.Forms.RadioButton();
            this.panel2 = new System.Windows.Forms.Panel();
            this.panel3 = new System.Windows.Forms.Panel();
            this.panel_used = new System.Windows.Forms.Panel();
            this.bt_Status = new System.Windows.Forms.Button();
            this.progressBar1 = new AutoMationTest.UI.XpProgressBar();
            this.panel1.SuspendLayout();
            this.panel2.SuspendLayout();
            this.panel3.SuspendLayout();
            this.SuspendLayout();
            // 
            // panel1
            // 
            this.panel1.BackColor = System.Drawing.Color.Silver;
            this.panel1.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle;
            this.panel1.Controls.Add(this.panel_connectStatus);
            this.panel1.Controls.Add(this.checkBox2);
            this.panel1.Controls.Add(this.checkBox_Used);
            this.panel1.Controls.Add(this.UINumber);
            this.panel1.Controls.Add(this.StationName);
            this.panel1.ForeColor = System.Drawing.SystemColors.Desktop;
            this.panel1.Location = new System.Drawing.Point(-2, -1);
            this.panel1.Name = "panel1";
            this.panel1.Size = new System.Drawing.Size(209, 21);
            this.panel1.TabIndex = 0;
            // 
            // panel_connectStatus
            // 
            this.panel_connectStatus.BackColor = System.Drawing.Color.Black;
            this.panel_connectStatus.CenterColor = System.Drawing.Color.LightGray;
            this.panel_connectStatus.Location = new System.Drawing.Point(182, 0);
            this.panel_connectStatus.Name = "panel_connectStatus";
            this.panel_connectStatus.Size = new System.Drawing.Size(25, 13);
            this.panel_connectStatus.SurroundColor = System.Drawing.Color.DarkGray;
            this.panel_connectStatus.TabIndex = 13;
            // 
            // checkBox2
            // 
            this.checkBox2.AutoSize = true;
            this.checkBox2.BackColor = System.Drawing.Color.Transparent;
            this.checkBox2.Font = new System.Drawing.Font("微軟正黑體", 9F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(136)));
            this.checkBox2.ForeColor = System.Drawing.Color.Black;
            this.checkBox2.Location = new System.Drawing.Point(124, 0);
            this.checkBox2.Name = "checkBox2";
            this.checkBox2.Size = new System.Drawing.Size(63, 20);
            this.checkBox2.TabIndex = 17;
            this.checkBox2.Text = "不報警";
            this.checkBox2.UseVisualStyleBackColor = false;
            this.checkBox2.CheckedChanged += new System.EventHandler(this.checkBox2_CheckedChanged);
            // 
            // checkBox_Used
            // 
            this.checkBox_Used.AutoSize = true;
            this.checkBox_Used.BackColor = System.Drawing.Color.Transparent;
            this.checkBox_Used.Font = new System.Drawing.Font("微軟正黑體", 9F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(136)));
            this.checkBox_Used.ForeColor = System.Drawing.Color.Black;
            this.checkBox_Used.Location = new System.Drawing.Point(77, 0);
            this.checkBox_Used.Name = "checkBox_Used";
            this.checkBox_Used.Size = new System.Drawing.Size(51, 20);
            this.checkBox_Used.TabIndex = 16;
            this.checkBox_Used.Text = "使用";
            this.checkBox_Used.UseVisualStyleBackColor = false;
            this.checkBox_Used.CheckedChanged += new System.EventHandler(this.checkBox1_CheckedChanged);
            // 
            // UINumber
            // 
            this.UINumber.BackColor = System.Drawing.Color.WhiteSmoke;
            this.UINumber.Enabled = false;
            this.UINumber.Font = new System.Drawing.Font("Calibri", 9F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.UINumber.Location = new System.Drawing.Point(1, -1);
            this.UINumber.Name = "UINumber";
            this.UINumber.Size = new System.Drawing.Size(21, 22);
            this.UINumber.TabIndex = 14;
            this.UINumber.Text = "1";
            this.UINumber.TextAlign = System.Windows.Forms.HorizontalAlignment.Center;
            // 
            // StationName
            // 
            this.StationName.AutoSize = true;
            this.StationName.BackColor = System.Drawing.Color.Transparent;
            this.StationName.Font = new System.Drawing.Font("Cambria", 8.25F, ((System.Drawing.FontStyle)((System.Drawing.FontStyle.Bold | System.Drawing.FontStyle.Italic))), System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.StationName.ForeColor = System.Drawing.Color.Black;
            this.StationName.Location = new System.Drawing.Point(24, 3);
            this.StationName.Name = "StationName";
            this.StationName.Size = new System.Drawing.Size(40, 12);
            this.StationName.TabIndex = 15;
            this.StationName.Text = "Station";
            // 
            // textBox_TOTAL
            // 
            this.textBox_TOTAL.BackColor = System.Drawing.Color.WhiteSmoke;
            this.textBox_TOTAL.BorderStyle = System.Windows.Forms.BorderStyle.None;
            this.textBox_TOTAL.Font = new System.Drawing.Font("新宋体", 8.25F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.textBox_TOTAL.Location = new System.Drawing.Point(0, 2);
            this.textBox_TOTAL.Name = "textBox_TOTAL";
            this.textBox_TOTAL.Size = new System.Drawing.Size(46, 13);
            this.textBox_TOTAL.TabIndex = 13;
            this.textBox_TOTAL.Text = "总数";
            this.textBox_TOTAL.TextAlign = System.Windows.Forms.HorizontalAlignment.Center;
            // 
            // textBox_NG
            // 
            this.textBox_NG.BackColor = System.Drawing.Color.WhiteSmoke;
            this.textBox_NG.BorderStyle = System.Windows.Forms.BorderStyle.None;
            this.textBox_NG.Font = new System.Drawing.Font("新宋体", 8.25F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.textBox_NG.Location = new System.Drawing.Point(0, 18);
            this.textBox_NG.Name = "textBox_NG";
            this.textBox_NG.Size = new System.Drawing.Size(46, 13);
            this.textBox_NG.TabIndex = 12;
            this.textBox_NG.Text = "不良";
            this.textBox_NG.TextAlign = System.Windows.Forms.HorizontalAlignment.Center;
            // 
            // textBox_YR
            // 
            this.textBox_YR.BackColor = System.Drawing.Color.WhiteSmoke;
            this.textBox_YR.BorderStyle = System.Windows.Forms.BorderStyle.None;
            this.textBox_YR.Font = new System.Drawing.Font("新宋体", 8.25F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.textBox_YR.Location = new System.Drawing.Point(0, 50);
            this.textBox_YR.Name = "textBox_YR";
            this.textBox_YR.Size = new System.Drawing.Size(46, 13);
            this.textBox_YR.TabIndex = 14;
            this.textBox_YR.Text = "良率";
            this.textBox_YR.TextAlign = System.Windows.Forms.HorizontalAlignment.Center;
            // 
            // button1
            // 
            this.button1.BackColor = System.Drawing.Color.Silver;
            this.button1.FlatAppearance.BorderColor = System.Drawing.Color.FromArgb(((int)(((byte)(192)))), ((int)(((byte)(192)))), ((int)(((byte)(255)))));
            this.button1.FlatAppearance.BorderSize = 0;
            this.button1.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
            this.button1.Font = new System.Drawing.Font("Cambria", 12F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.button1.Image = ((System.Drawing.Image)(resources.GetObject("button1.Image")));
            this.button1.Location = new System.Drawing.Point(2, 68);
            this.button1.Name = "button1";
            this.button1.Size = new System.Drawing.Size(44, 23);
            this.button1.TabIndex = 19;
            this.button1.UseVisualStyleBackColor = false;
            this.button1.Click += new System.EventHandler(this.button1_Click);
            // 
            // textBox_LianxuNG
            // 
            this.textBox_LianxuNG.BackColor = System.Drawing.Color.WhiteSmoke;
            this.textBox_LianxuNG.BorderStyle = System.Windows.Forms.BorderStyle.None;
            this.textBox_LianxuNG.Font = new System.Drawing.Font("新宋体", 8.25F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.textBox_LianxuNG.Location = new System.Drawing.Point(0, 34);
            this.textBox_LianxuNG.Name = "textBox_LianxuNG";
            this.textBox_LianxuNG.Size = new System.Drawing.Size(46, 13);
            this.textBox_LianxuNG.TabIndex = 20;
            this.textBox_LianxuNG.Text = "连续不良";
            this.textBox_LianxuNG.TextAlign = System.Windows.Forms.HorizontalAlignment.Center;
            // 
            // radioButton1
            // 
            this.radioButton1.AutoSize = true;
            this.radioButton1.Checked = true;
            this.radioButton1.Location = new System.Drawing.Point(12, -1);
            this.radioButton1.Name = "radioButton1";
            this.radioButton1.Size = new System.Drawing.Size(61, 18);
            this.radioButton1.TabIndex = 22;
            this.radioButton1.TabStop = true;
            this.radioButton1.Text = "正常品";
            this.radioButton1.UseVisualStyleBackColor = true;
            this.radioButton1.CheckedChanged += new System.EventHandler(this.radioButton1_CheckedChanged);
            // 
            // radioButton2
            // 
            this.radioButton2.AutoSize = true;
            this.radioButton2.ForeColor = System.Drawing.Color.Maroon;
            this.radioButton2.Location = new System.Drawing.Point(84, -1);
            this.radioButton2.Name = "radioButton2";
            this.radioButton2.Size = new System.Drawing.Size(61, 18);
            this.radioButton2.TabIndex = 23;
            this.radioButton2.Text = "標準件";
            this.radioButton2.UseVisualStyleBackColor = true;
            // 
            // panel2
            // 
            this.panel2.BackColor = System.Drawing.Color.Silver;
            this.panel2.BorderStyle = System.Windows.Forms.BorderStyle.Fixed3D;
            this.panel2.Controls.Add(this.radioButton1);
            this.panel2.Controls.Add(this.radioButton2);
            this.panel2.Enabled = false;
            this.panel2.Location = new System.Drawing.Point(-1, 73);
            this.panel2.Name = "panel2";
            this.panel2.Size = new System.Drawing.Size(157, 20);
            this.panel2.TabIndex = 24;
            // 
            // panel3
            // 
            this.panel3.BackColor = System.Drawing.Color.Transparent;
            this.panel3.BorderStyle = System.Windows.Forms.BorderStyle.Fixed3D;
            this.panel3.Controls.Add(this.textBox_LianxuNG);
            this.panel3.Controls.Add(this.textBox_YR);
            this.panel3.Controls.Add(this.textBox_NG);
            this.panel3.Controls.Add(this.textBox_TOTAL);
            this.panel3.Controls.Add(this.button1);
            this.panel3.Enabled = false;
            this.panel3.Location = new System.Drawing.Point(155, 18);
            this.panel3.Name = "panel3";
            this.panel3.Size = new System.Drawing.Size(51, 99);
            this.panel3.TabIndex = 25;
            // 
            // panel_used
            // 
            this.panel_used.BackgroundImage = ((System.Drawing.Image)(resources.GetObject("panel_used.BackgroundImage")));
            this.panel_used.BackgroundImageLayout = System.Windows.Forms.ImageLayout.Zoom;
            this.panel_used.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle;
            this.panel_used.Location = new System.Drawing.Point(-1, 19);
            this.panel_used.Name = "panel_used";
            this.panel_used.Size = new System.Drawing.Size(209, 97);
            this.panel_used.TabIndex = 28;
            // 
            // bt_Status
            // 
            this.bt_Status.Font = new System.Drawing.Font("Georgia", 18F, System.Drawing.FontStyle.Bold);
            this.bt_Status.Location = new System.Drawing.Point(-1, 18);
            this.bt_Status.Name = "bt_Status";
            this.bt_Status.Size = new System.Drawing.Size(158, 58);
            this.bt_Status.TabIndex = 0;
            this.bt_Status.Text = "No Used";
            // 
            // progressBar1
            // 
            this.progressBar1.ColorBackGround = System.Drawing.Color.White;
            this.progressBar1.ColorBarBorder = System.Drawing.Color.White;
            this.progressBar1.ColorBarCenter = System.Drawing.Color.SkyBlue;
            this.progressBar1.ColorsXP = false;
            this.progressBar1.ColorText = System.Drawing.Color.Gray;
            this.progressBar1.Enabled = false;
            this.progressBar1.Font = new System.Drawing.Font("Calibri", 9F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.progressBar1.ForeColor = System.Drawing.SystemColors.ActiveCaptionText;
            this.progressBar1.Location = new System.Drawing.Point(0, 93);
            this.progressBar1.Name = "progressBar1";
            this.progressBar1.Position = 0;
            this.progressBar1.PositionMax = 100;
            this.progressBar1.PositionMin = 0;
            this.progressBar1.Size = new System.Drawing.Size(156, 22);
            this.progressBar1.SteepDistance = ((byte)(0));
            this.progressBar1.SteepWidth = ((byte)(1));
            this.progressBar1.TabIndex = 26;
            this.progressBar1.Text = "SN";
            this.progressBar1.TextShadow = false;
            this.progressBar1.TextShadowAlpha = ((byte)(100));
            // 
            // TestUI
            // 
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.None;
            this.BackColor = System.Drawing.Color.Gainsboro;
            this.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle;
            this.Controls.Add(this.panel_used);
            this.Controls.Add(this.panel3);
            this.Controls.Add(this.panel2);
            this.Controls.Add(this.panel1);
            this.Controls.Add(this.bt_Status);
            this.Controls.Add(this.progressBar1);
            this.DoubleBuffered = true;
            this.Font = new System.Drawing.Font("Calibri", 9F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.Name = "TestUI";
            this.Size = new System.Drawing.Size(207, 115);
            this.Load += new System.EventHandler(this.TestUI_Load);
            this.panel1.ResumeLayout(false);
            this.panel1.PerformLayout();
            this.panel2.ResumeLayout(false);
            this.panel2.PerformLayout();
            this.panel3.ResumeLayout(false);
            this.panel3.PerformLayout();
            this.ResumeLayout(false);

        }

        #endregion

        private System.Windows.Forms.Panel panel1;
        public JianBianPanel panel_connectStatus;
        private System.Windows.Forms.CheckBox checkBox2;
        public System.Windows.Forms.TextBox UINumber;
        public System.Windows.Forms.Label StationName;
        public System.Windows.Forms.TextBox textBox_TOTAL;
        public System.Windows.Forms.TextBox textBox_NG;
        public System.Windows.Forms.TextBox textBox_YR;
        private System.Windows.Forms.Button button1;
        public System.Windows.Forms.TextBox textBox_LianxuNG;
        private System.Windows.Forms.Panel panel2;
        private System.Windows.Forms.Panel panel3;
        public XpProgressBar progressBar1;
        public System.Windows.Forms.CheckBox checkBox_Used;
        private System.Windows.Forms.Button bt_Status;// private System.Windows.Forms.Button
        private System.Windows.Forms.Panel panel_used;
        public System.Windows.Forms.RadioButton radioButton1;
        public System.Windows.Forms.RadioButton radioButton2;
    }
}
