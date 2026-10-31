import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ComposedChart,
} from 'recharts';

interface ChartProps {
  data: any[];
  width?: number;
  height?: number;
  className?: string;
}

interface ChartSeries {
  key: string;
  label: string;
  color?: string;
}

const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];

export function LineChartComponent({ data, width, height = 300, className, lines }: ChartProps & { lines: ChartSeries[] }) {
  return (
    <div className={className} style={{ width: width || '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} tick={{ fill: '#64748b' }} />
          <YAxis stroke="#94a3b8" fontSize={12} tick={{ fill: '#64748b' }} />
          <Tooltip
            contentStyle={{
              backgroundColor: 'white',
              border: '1px solid #e2e8f0',
              borderRadius: '8px',
              boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
            }}
            labelStyle={{ color: '#1e293b', fontWeight: 600 }}
          />
          <Legend />
          {lines.map((line, index) => (
            <Line
              key={line.key}
              type="monotone"
              dataKey={line.key}
              name={line.label}
              stroke={line.color || COLORS[index % COLORS.length]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 6 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function BarChartComponent({ data, width, height = 300, className, keys, labels }: ChartProps & { keys: string[]; labels: string[] }) {
  return (
    <div className={className} style={{ width: width || '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} tick={{ fill: '#64748b' }} />
          <YAxis stroke="#94a3b8" fontSize={12} tick={{ fill: '#64748b' }} />
          <Tooltip
            contentStyle={{
              backgroundColor: 'white',
              border: '1px solid #e2e8f0',
              borderRadius: '8px',
              boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
            }}
            labelStyle={{ color: '#1e293b', fontWeight: 600 }}
          />
          <Legend />
          {keys.map((key, index) => (
            <Bar
              key={key}
              dataKey={key}
              name={labels[index] || key}
              fill={COLORS[index % COLORS.length]}
              radius={[4, 4, 0, 0]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function AreaChartComponent({ data, width, height = 300, className, keys, labels }: ChartProps & { keys: string[]; labels: string[] }) {
  return (
    <div className={className} style={{ width: width || '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} tick={{ fill: '#64748b' }} />
          <YAxis stroke="#94a3b8" fontSize={12} tick={{ fill: '#64748b' }} />
          <Tooltip
            contentStyle={{
              backgroundColor: 'white',
              border: '1px solid #e2e8f0',
              borderRadius: '8px',
              boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
            }}
            labelStyle={{ color: '#1e293b', fontWeight: 600 }}
          />
          <Legend />
          {keys.map((key, index) => (
            <Area
              key={key}
              type="monotone"
              dataKey={key}
              name={labels[index] || key}
              stroke={COLORS[index % COLORS.length]}
              fill={COLORS[index % COLORS.length]}
              fillOpacity={0.3}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function DonutChartComponent({ data, width, height = 300, className, nameKey, valueKey, colors }: ChartProps & { nameKey: string; valueKey: string; colors?: string[] }) {
  return (
    <div className={className} style={{ width: width || '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={100}
            fill="#8884d8"
            paddingAngle={2}
            dataKey={valueKey}
            nameKey={nameKey}
            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
            labelLine={false}
          >
            {data.map((_, index) => (
              <Cell key={`cell-${index}`} fill={colors?.[index] || COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: 'white',
              border: '1px solid #e2e8f0',
              borderRadius: '8px',
              boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
            }}
            formatter={(value: number) => [value.toLocaleString(), '']}
          />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ComposedChartComponent({ data, width, height = 300, className, bars, lines }: ChartProps & {
  bars: ChartSeries[];
  lines: ChartSeries[];
}) {
  return (
    <div className={className} style={{ width: width || '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} tick={{ fill: '#64748b' }} />
          <YAxis
            yAxisId="left"
            stroke="#94a3b8"
            fontSize={12}
            tick={{ fill: '#64748b' }}
            orientation="left"
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            stroke="#94a3b8"
            fontSize={12}
            tick={{ fill: '#64748b' }}
            domain={['auto', 'auto']}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'white',
              border: '1px solid #e2e8f0',
              borderRadius: '8px',
              boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
            }}
            labelStyle={{ color: '#1e293b', fontWeight: 600 }}
          />
          <Legend />
          {bars.map((bar, index) => (
            <Bar
              key={bar.key}
              dataKey={bar.key}
              name={bar.label}
              yAxisId="left"
              fill={bar.color || COLORS[index % COLORS.length]}
              radius={[4, 4, 0, 0]}
            />
          ))}
          {lines.map((line, index) => (
            <Line
              key={line.key}
              type="monotone"
              dataKey={line.key}
              name={line.label}
              yAxisId="right"
              stroke={line.color || COLORS[(index + bars.length) % COLORS.length]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 6 }}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}