# Development-only oracle executing unmodified methods from the pinned Rails source.
# Stand-ins supply only ActiveSupport value helpers, params, and an in-memory model.
require 'json'
require 'set'
require 'ostruct'
require 'pathname'
root = Pathname.new(__dir__).join('../../..').realpath
source = root.join('vendor/badgeapp-m3')
class Object
  def blank?; respond_to?(:empty?) ? !!empty? : !self; end
  def present?; !blank?; end
  def presence; present? ? self : nil; end
end
class String
  def blank?; empty? || /\A[[:space:]]*\z/.match?(self); end
end
class Set
  def exclude?(value); !include?(value); end
end
load source.join('lib/criterion_status.rb')
class Params < Hash
  def [](key); super(key.to_s); end
end
class ControllerOracle
  EMPTY_FROZEN_SET = Set.new.freeze
  attr_accessor :params
  def run(saved, proposed, overrides)
    self.params = Params[proposed.merge('overrides' => overrides.join(','))]
    @project = OpenStruct.new(saved.transform_keys(&:to_sym))
    @automated_fields, @overridden_fields, @divergent_fields = {}, {}, {}
    valid = Set.new(proposed.keys.map(&:to_sym))
    forced = compute_forced_fields(valid)
    originals = snapshot_original_values(valid)
    proposals = build_url_proposals(valid, forced)
    divergent = classify_status_pass(proposals, originals, track_automated: true)
    classify_non_status_pass(proposals, originals, divergent, track_automated: true)
    apply_url_proposals(proposals, originals, divergent)
    { 'saved_after' => @project.to_h, 'blocked_statuses' => divergent.to_a,
      'effective_overrides' => forced.to_a.sort }
  end
end
controller = source.join('app/controllers/projects_controller.rb').read
# Each slice ends at the next two-space method declaration, retaining exact bodies/comments.
%w[compute_forced_fields snapshot_original_values build_url_proposals classify_status_pass classify_non_status_pass apply_url_proposals parse_status_value].each do |name|
  start = controller.index(/^  def #{name}[\s(]/)
  stop = controller.index(/^  def /, start + 6)
  ControllerOracle.class_eval(controller[start...stop], 'pinned_projects_controller.rb')
end
class PredicateOracle
  MIN_SHOULD_LENGTH = 5 # pinned Project constant (source hash checked by tests)
end
model = source.join('app/models/project.rb').read
%w[contains_url? justification_good?].each do |name|
  start = model.index("  def #{name}(")
  stop = model.index(/^  def /, start + 6)
  PredicateOracle.class_eval(model[start...stop], 'pinned_project.rb')
end
status = 'description_good_status'
just = 'description_good_justification'
cases = []
['?', 'Met', 'Unmet'].product(['Met', 'Unmet'], ['', 'old explanation', 'new explanation'], [[], [status], [just], [status, just]], ['new explanation', "\t new explanation \n", "\u00a0new explanation\u00a0"]).each do |old, proposal, old_text, overrides, new_text|
  saved = {status => old, just => old_text}
  draft = {status => proposal, just => new_text}
  ints = saved.merge(status => CriterionStatus.parse(old))
  result = ControllerOracle.new.run(ints, draft, overrides)
  result['saved_after'][status.to_sym] = CriterionStatus::STATUS_VALUES[result['saved_after'][status.to_sym]]
  cases << {'record' => saved, 'draft' => draft, 'overrides' => overrides, 'expected' => result}
end
predicate = PredicateOracle.new
texts = [nil, '', 'abcd', 'abcde', '     ', '// explanation', '// https://example.org', "\n// https://example.org", 'prefix https://a.b suffix', 'http://localhost', 'https://example.org', 'HTTPS://example.org', "https://a.\n", "\u00a0\u00a0\u00a0\u00a0\u00a0"]
result = {
 'revision' => JSON.parse(source.join('source.json').read)['revision'],
 'oracle' => 'Pinned Ruby controller methods and Project predicates with minimal ActiveSupport stand-ins; no Python implementation imports',
 'cases' => cases,
 'predicates' => texts.map { |text| {'text' => text, 'justification_good' => !!predicate.justification_good?(text), 'contains_url' => !!predicate.contains_url?(text)} }
}
# JSON 2.1 emits a blank line inside empty arrays; newer JSON releases emit [].
# Normalize serializer whitespace only; JSON string newlines are already escaped.
output = JSON.pretty_generate(result).gsub(/\[\n\n *\]/, '[]') + "\n"
path = root.join('tests/fixtures/upstream/m3_oracle.json')
if ARGV.include?('--check')
  abort 'M3 oracle differs; regenerate and review upstream drift' unless path.read == output
  puts "Pinned Ruby M3 oracle reproducible: #{cases.length} transfers, #{texts.length} predicates"
else
  path.write(output)
  puts "Wrote #{cases.length} transfers and #{texts.length} predicates"
end
