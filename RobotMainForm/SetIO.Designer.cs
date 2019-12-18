namespace AutoMationTest.UI
{
    partial class SetIO
    {
        /// <summary>
        /// Required designer variable.
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary>
        /// Clean up any resources being used.
        /// </summary>
        /// <param name="disposing">true if managed resources should be disposed; otherwise, false.</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region Windows Form Designer generated code

        /// <summary>
        /// Required method for Designer support - do not modify
        /// the contents of this method with the code editor.
        /// </summary>
        private void InitializeComponent()
        {
            this.label1 = new System.Windows.Forms.Label();
            this.button1 = new System.Windows.Forms.Button();
            this.label2 = new System.Windows.Forms.Label();
            this.label3 = new System.Windows.Forms.Label();
            this.nupdown_port = new System.Windows.Forms.NumericUpDown();
            this.nupdown_num = new System.Windows.Forms.NumericUpDown();
            this.tBox_name = new System.Windows.Forms.TextBox();
            this.label4 = new System.Windows.Forms.Label();
            this.bt_id = new System.Windows.Forms.Button();
            ((System.ComponentModel.ISupportInitialize)(this.nupdown_port)).BeginInit();
            ((System.ComponentModel.ISupportInitialize)(this.nupdown_num)).BeginInit();
            this.SuspendLayout();
            // 
            // label1
            // 
            this.label1.AutoSize = true;
            this.label1.Font = new System.Drawing.Font("微软雅黑", 14.25F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.label1.Location = new System.Drawing.Point(124, 9);
            this.label1.Name = "label1";
            this.label1.Size = new System.Drawing.Size(88, 25);
            this.label1.TabIndex = 0;
            this.label1.Text = "輸入設置";
            // 
            // button1
            // 
            this.button1.BackColor = System.Drawing.Color.WhiteSmoke;
            this.button1.DialogResult = System.Windows.Forms.DialogResult.OK;
            this.button1.Font = new System.Drawing.Font("微软雅黑", 11.25F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.button1.Location = new System.Drawing.Point(290, 47);
            this.button1.Name = "button1";
            this.button1.Size = new System.Drawing.Size(64, 65);
            this.button1.TabIndex = 3;
            this.button1.Text = "更改";
            this.button1.UseVisualStyleBackColor = false;
            this.button1.Click += new System.EventHandler(this.button1_Click);
            // 
            // label2
            // 
            this.label2.AutoSize = true;
            this.label2.ForeColor = System.Drawing.Color.DarkCyan;
            this.label2.Location = new System.Drawing.Point(34, 89);
            this.label2.Name = "label2";
            this.label2.Size = new System.Drawing.Size(35, 19);
            this.label2.TabIndex = 4;
            this.label2.Text = "Port";
            // 
            // label3
            // 
            this.label3.AutoSize = true;
            this.label3.ForeColor = System.Drawing.Color.DarkCyan;
            this.label3.Location = new System.Drawing.Point(148, 89);
            this.label3.Name = "label3";
            this.label3.Size = new System.Drawing.Size(40, 19);
            this.label3.TabIndex = 5;
            this.label3.Text = "Num";
            // 
            // nupdown_port
            // 
            this.nupdown_port.Location = new System.Drawing.Point(75, 87);
            this.nupdown_port.Maximum = new decimal(new int[] {
            7,
            0,
            0,
            0});
            this.nupdown_port.Name = "nupdown_port";
            this.nupdown_port.Size = new System.Drawing.Size(63, 25);
            this.nupdown_port.TabIndex = 6;
            // 
            // nupdown_num
            // 
            this.nupdown_num.Location = new System.Drawing.Point(194, 87);
            this.nupdown_num.Maximum = new decimal(new int[] {
            7,
            0,
            0,
            0});
            this.nupdown_num.Name = "nupdown_num";
            this.nupdown_num.Size = new System.Drawing.Size(63, 25);
            this.nupdown_num.TabIndex = 7;
            // 
            // tBox_name
            // 
            this.tBox_name.Location = new System.Drawing.Point(75, 47);
            this.tBox_name.Name = "tBox_name";
            this.tBox_name.Size = new System.Drawing.Size(182, 25);
            this.tBox_name.TabIndex = 8;
            // 
            // label4
            // 
            this.label4.AutoSize = true;
            this.label4.ForeColor = System.Drawing.Color.DarkCyan;
            this.label4.Location = new System.Drawing.Point(23, 50);
            this.label4.Name = "label4";
            this.label4.Size = new System.Drawing.Size(46, 19);
            this.label4.TabIndex = 9;
            this.label4.Text = "Name";
            // 
            // bt_id
            // 
            this.bt_id.Enabled = false;
            this.bt_id.Location = new System.Drawing.Point(290, 7);
            this.bt_id.Name = "bt_id";
            this.bt_id.Size = new System.Drawing.Size(64, 32);
            this.bt_id.TabIndex = 10;
            this.bt_id.Text = "0";
            this.bt_id.UseVisualStyleBackColor = true;
            // 
            // SetIO
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(8F, 19F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(371, 129);
            this.Controls.Add(this.bt_id);
            this.Controls.Add(this.label4);
            this.Controls.Add(this.tBox_name);
            this.Controls.Add(this.nupdown_num);
            this.Controls.Add(this.nupdown_port);
            this.Controls.Add(this.label3);
            this.Controls.Add(this.label2);
            this.Controls.Add(this.button1);
            this.Controls.Add(this.label1);
            this.Font = new System.Drawing.Font("微软雅黑", 9.75F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.FormBorderStyle = System.Windows.Forms.FormBorderStyle.FixedToolWindow;
            this.Margin = new System.Windows.Forms.Padding(4, 5, 4, 5);
            this.Name = "SetIO";
            this.StartPosition = System.Windows.Forms.FormStartPosition.Manual;
            this.Text = "SetIO";
            ((System.ComponentModel.ISupportInitialize)(this.nupdown_port)).EndInit();
            ((System.ComponentModel.ISupportInitialize)(this.nupdown_num)).EndInit();
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private System.Windows.Forms.Label label1;
        private System.Windows.Forms.Button button1;
        private System.Windows.Forms.Label label2;
        private System.Windows.Forms.Label label3;
        private System.Windows.Forms.NumericUpDown nupdown_port;
        private System.Windows.Forms.NumericUpDown nupdown_num;
        private System.Windows.Forms.TextBox tBox_name;
        private System.Windows.Forms.Label label4;
        private System.Windows.Forms.Button bt_id;
    }
}