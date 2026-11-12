# Development-only independent oracle: run with Ruby/Psych, not the Python generator.
# It executes the pinned upstream details-inheritance and display-ID methods.
# The committed JSON fixture is consumed by Python tests; Ruby is not required there.
require 'yaml'
require 'json'
require 'pathname'

root = Pathname.new(__dir__).join('../../..').realpath
source = root.join('vendor/badgeapp')
manifest = JSON.parse(source.join('source.json').read)
metal = YAML.load_file(source.join('criteria/criteria.yml'))
baseline = YAML.load_file(source.join('criteria/baseline_criteria.yml'))
baseline.delete('_metadata')
levels = metal.merge(baseline)
english = YAML.load_file(source.join('config/locales/en.yml'))['en']['criteria']
definitions = levels.transform_values do |majors|
  majors.values.flat_map(&:values).reduce({}, :merge)
end

# Minimal adapters supply the Rails helpers used by the two upstream methods.
class Object
  def in?(collection)
    collection.include?(self)
  end
end
class String
  def html_safe
    self
  end
end
module I18n
  class << self
    attr_accessor :data
    def exists?(key)
      !t(key).nil?
    end
    def t(key)
      key.split('.').drop(1).reduce(data) { |value, segment| value && value[segment] }
    end
  end
end
I18n.data = english
load source.join('app/models/concerns/level_conversion.rb')
class Criteria
  include LevelConversion
  LOCALE_ACCESSORS = %i[description details met_placeholder unmet_placeholder na_placeholder].freeze
  attr_accessor :name, :level
  class << self
    attr_accessor :definitions
    def get_levels(name)
      definitions.keys.select { |level| definitions[level].key?(name) }
    end
  end
end
Criteria.definitions = definitions
upstream = source.join('app/models/criteria.rb').read
methods = upstream[upstream.index('  def get_text_if_exists(field)')...upstream.rindex("\nend")]
Criteria.class_eval(methods)
module DisplayOracle; end
helper = source.join('app/helpers/projects_helper.rb').read
method_start = helper.index('  def self.compute_baseline_display_name(id_str)')
method_end = helper.index('  private_class_method :compute_baseline_display_name', method_start)
DisplayOracle.module_eval(helper[method_start...method_end])

level_names = { '0' => 'passing', '1' => 'silver', '2' => 'gold' }
flags = %w[na_allowed na_justification_required met_justification_required met_url_required]
records = definitions.flat_map do |level, criteria|
  criteria.sort.map do |id, raw|
    instance = Criteria.new
    instance.name = id
    instance.level = level
    display = DisplayOracle.compute_baseline_display_name(id)
    {
      'level' => level_names.fetch(level, level),
      'criterion_id' => id,
      'description' => english.fetch(level).fetch(id).fetch('description'),
      'details' => instance.send(:get_text_if_exists, :details),
      'requirement' => raw.fetch('category'),
      'aliases' => display == id ? [] : [display]
    }.merge(flags.to_h { |flag| [flag, raw[flag] == true] })
  end
end
result = {
  'source_revision' => manifest.fetch('revision'),
  'oracle' => 'Ruby/Psych with pinned Criteria#get_text_if_exists and ProjectsHelper.compute_baseline_display_name',
  'records' => records
}
root.join('tests/fixtures/upstream/criteria_oracle.json').write(JSON.pretty_generate(result) + "\n")
puts "Wrote #{records.length} independent criterion expectations"
